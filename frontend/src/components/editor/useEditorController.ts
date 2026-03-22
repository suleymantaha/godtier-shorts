import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type SyntheticEvent } from 'react';

import { clipsApi, editorApi } from '../../api/client';
import { MAX_UPLOAD_BYTES } from '../../config';
import { useDebouncedEffect } from '../../hooks/useDebouncedEffect';
import { useThrottledCallback } from '../../hooks/useThrottle';
import { tSafe } from '../../i18n';
import { useJobStore } from '../../store/useJobStore';
import type { Clip, Job, Segment } from '../../types';
import { normalizeTranscript, syncSegmentTextAndWords } from '../../utils/transcript';
import { isStyleName, isSubtitleAnimationType } from '../../config/subtitleStyles';
import {
  buildEditorSessionKey,
  buildStoredEditorSession,
  clampLoadedMetadataEndTime,
  filterTranscriptForManualRender,
  findTranscriptIndexAtTime,
  formatUploadLimit,
  getErrorMessage,
  getTimeRangeError,
  getVisibleTranscriptEntries,
  readStoredEditorSession,
  resolveClipProjectId,
  resolveEditorVideoSrc,
  resolveStoredEditorState,
  type ResolvedEditorSessionState,
} from './helpers';

export interface EditorProps {
  mode?: 'master' | 'clip';
  onClose?: () => void;
  targetClip?: Clip;
}

function useLocalPreviewSource() {
  const [localSrc, setLocalSrc] = useState<string | null>(null);
  const localBlobUrlRef = useRef<string | null>(null);

  const setLocalSrcWithCleanup = useCallback((nextSrc: string | null) => {
    setLocalSrc((previousSrc) => {
      if (previousSrc && previousSrc !== nextSrc && previousSrc.startsWith('blob:')) {
        URL.revokeObjectURL(previousSrc);
      }

      return nextSrc;
    });

    localBlobUrlRef.current = nextSrc && nextSrc.startsWith('blob:') ? nextSrc : null;
  }, []);

  useEffect(() => () => {
    if (localBlobUrlRef.current) {
      URL.revokeObjectURL(localBlobUrlRef.current);
      localBlobUrlRef.current = null;
    }
  }, []);

  return { localSrc, setLocalSrcWithCleanup };
}

function useEditorState(initialProjectId: string | undefined) {
  const [uploading, setUploading] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [transcript, setTranscript] = useState<Segment[]>([]);
  const [saving, setSaving] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startTime, setStartTime] = useState(0);
  const [endTime, setEndTime] = useState(60);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [style, setStyle] = useState<ResolvedEditorSessionState['style']>('HORMOZI');
  const [animationType, setAnimationType] = useState<ResolvedEditorSessionState['animationType']>('default');
  const [numClips, setNumClips] = useState(3);
  const [centerX, setCenterX] = useState(0.5);
  const [projectId, setProjectId] = useState<string | undefined>(initialProjectId);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  return {
    animationType,
    centerX,
    currentJobId,
    currentTime,
    duration,
    endTime,
    error,
    fileInputRef,
    isPlaying,
    numClips,
    processing,
    projectId,
    saving,
    sessionReady,
    setCenterX,
    setCurrentJobId,
    setCurrentTime,
    setDuration,
    setEndTime,
    setError,
    setAnimationType,
    setIsPlaying,
    setNumClips,
    setProcessing,
    setProjectId,
    setSaving,
    setSessionReady,
    setStartTime,
    setStyle,
    setTranscribing,
    setTranscript,
    setUploading,
    startTime,
    style,
    transcript,
    transcribing,
    uploading,
    videoRef,
  };
}

interface EditorEffectsParams {
  clipProjectId: string | undefined;
  jobs: Job[];
  mode: 'master' | 'clip';
  sessionKey: string;
  setLocalSrcWithCleanup: (nextSrc: string | null) => void;
  state: ReturnType<typeof useEditorState>;
  targetClip?: Clip;
}

function useHydrateEditorSessionEffect({
  clipProjectId,
  mode,
  sessionKey,
  setLocalSrcWithCleanup,
  state,
  targetClip,
}: Omit<EditorEffectsParams, 'jobs'>) {
  const {
    setAnimationType,
    setCenterX,
    setCurrentJobId,
    setEndTime,
    setError,
    setNumClips,
    setProjectId,
    setSessionReady,
    setStartTime,
    setStyle,
    setTranscript,
  } = state;

  useEffect(() => {
    setSessionReady(false);
    setError(null);
    setLocalSrcWithCleanup(null);

    const nextState = resolveStoredEditorState(mode, targetClip, clipProjectId, readStoredEditorSession(sessionKey));
    setProjectId(nextState.projectId);
    setTranscript(nextState.transcript);
    setStartTime(nextState.startTime);
    setEndTime(nextState.endTime);
    setStyle(nextState.style);
    setAnimationType(nextState.animationType);
    setNumClips(nextState.numClips);
    setCenterX(nextState.centerX);
    setCurrentJobId(nextState.currentJobId);

    if (nextState.clearPersistedSession && typeof window !== 'undefined') {
      window.localStorage.removeItem(sessionKey);
    }

    setSessionReady(true);
  }, [
    clipProjectId,
    mode,
    sessionKey,
    setCenterX,
    setCurrentJobId,
    setEndTime,
    setError,
    setLocalSrcWithCleanup,
    setNumClips,
    setProjectId,
    setSessionReady,
    setStartTime,
    setAnimationType,
    setStyle,
    setTranscript,
    targetClip,
  ]);
}

function usePersistEditorSessionEffect({ sessionKey, state }: Pick<EditorEffectsParams, 'sessionKey' | 'state'>) {
  useDebouncedEffect(() => {
    if (typeof window === 'undefined' || !state.sessionReady) {
      return;
    }

    window.localStorage.setItem(sessionKey, JSON.stringify(buildStoredEditorSession({
      centerX: state.centerX,
      animationType: state.animationType,
      currentJobId: state.currentJobId,
      endTime: state.endTime,
      numClips: state.numClips,
      projectId: state.projectId,
      startTime: state.startTime,
      style: state.style,
      transcript: state.transcript,
    })));
  }, [
    sessionKey,
    state.centerX,
    state.animationType,
    state.currentJobId,
    state.endTime,
    state.numClips,
    state.projectId,
    state.sessionReady,
    state.startTime,
    state.style,
    state.transcript,
  ], 500);
}

function useProjectTranscriptEffect({ state }: Pick<EditorEffectsParams, 'state'>) {
  const { projectId, sessionReady, setTranscript, transcript } = state;

  useEffect(() => {
    if (!sessionReady || !projectId || transcript.length > 0) {
      return;
    }

    const loadTranscript = async () => {
      try {
        setTranscript(normalizeTranscript(await editorApi.getTranscript(projectId)));
      } catch (error) {
        console.error('Transkript yüklenirken hata:', error);
      }
    };

    void loadTranscript();
  }, [projectId, sessionReady, setTranscript, transcript.length]);
}

function useTrackEditorJobEffect({ jobs, state }: Pick<EditorEffectsParams, 'jobs' | 'state'>) {
  const {
    currentJobId,
    projectId,
    sessionReady,
    setCurrentJobId,
    setError,
    setProcessing,
    setTranscript,
    setTranscribing,
  } = state;

  useEffect(() => {
    if (!sessionReady || !currentJobId) {
      return;
    }

    const job = jobs.find((item) => item.job_id === currentJobId);
    if (!job) {
      return;
    }

    if (job.status === 'completed') {
      setProcessing(false);
      setTranscribing(false);
      if (currentJobId.startsWith('upload') && projectId) {
        void editorApi.getTranscript(projectId)
          .then((response) => setTranscript(normalizeTranscript(response)))
          .catch((error) => console.error('Transkript yüklenirken hata:', error));
      }
      setCurrentJobId(null);
      return;
    }

    if (job.status === 'error' || job.status === 'cancelled') {
      setProcessing(false);
      setTranscribing(false);
      setError(job.last_message || 'İşlem başarısız.');
      setCurrentJobId(null);
    }
  }, [
    currentJobId,
    jobs,
    projectId,
    sessionReady,
    setCurrentJobId,
    setError,
    setProcessing,
    setTranscript,
    setTranscribing,
  ]);
}

function useClipTranscriptEffect({
  clipProjectId,
  mode,
  setAnimationType,
  state,
  setStyle,
  targetClip,
}: Pick<EditorEffectsParams, 'clipProjectId' | 'mode' | 'state' | 'targetClip'> & {
  setAnimationType: React.Dispatch<React.SetStateAction<ResolvedEditorSessionState['animationType']>>;
  setStyle: React.Dispatch<React.SetStateAction<ResolvedEditorSessionState['style']>>;
}) {
  const { sessionReady, setError, setTranscript, transcript } = state;

  useEffect(() => {
    if (!sessionReady || mode !== 'clip' || !targetClip || transcript.length > 0) {
      return;
    }

    if (!clipProjectId) {
      setError('Bu klip icin proje baglami bulunamadi.');
      return;
    }

    void clipsApi.getTranscript(targetClip.name, clipProjectId)
      .then((response) => {
        setTranscript(normalizeTranscript(response));
        const renderMetadata = response.render_metadata;
        if (renderMetadata?.style_name && isStyleName(renderMetadata.style_name)) {
          setStyle(renderMetadata.style_name);
        }
        if (renderMetadata?.animation_type && isSubtitleAnimationType(renderMetadata.animation_type)) {
          setAnimationType(renderMetadata.animation_type);
        }
      })
      .catch((error) => setError(getErrorMessage(error, 'Transkript yüklenemedi.')));
  }, [clipProjectId, mode, sessionReady, setAnimationType, setError, setStyle, setTranscript, targetClip, transcript.length]);
}

function useEditorEffects(params: EditorEffectsParams) {
  useHydrateEditorSessionEffect(params);
  usePersistEditorSessionEffect(params);
  useProjectTranscriptEffect(params);
  useTrackEditorJobEffect(params);
  useClipTranscriptEffect({
    ...params,
    setAnimationType: params.state.setAnimationType,
    setStyle: params.state.setStyle,
  });
}

function useEditorPlaybackActions({
  endTime,
  setDuration,
  setEndTime,
  startTime,
  videoRef,
}: {
  endTime: number;
  setDuration: React.Dispatch<React.SetStateAction<number>>;
  setEndTime: React.Dispatch<React.SetStateAction<number>>;
  startTime: number;
  videoRef: React.RefObject<HTMLVideoElement | null>;
}) {
  const togglePlay = useCallback(() => {
    if (!videoRef.current) {
      return;
    }

    if (videoRef.current.paused) {
      void videoRef.current.play();
      return;
    }

    videoRef.current.pause();
  }, [videoRef]);

  const handleLoadedMetadata = useCallback((event: SyntheticEvent<HTMLVideoElement>) => {
    const nextDuration = event.currentTarget.duration;
    setDuration(nextDuration);
    setEndTime(clampLoadedMetadataEndTime(nextDuration));
  }, [setDuration, setEndTime]);

  const jumpToStart = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.currentTime = startTime;
    }
  }, [startTime, videoRef]);

  const jumpToEnd = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.currentTime = endTime - 3;
    }
  }, [endTime, videoRef]);

  return { handleLoadedMetadata, jumpToEnd, jumpToStart, togglePlay };
}

function useEditorTimeline({
  setCurrentTime,
  transcript,
  videoRef,
}: {
  setCurrentTime: React.Dispatch<React.SetStateAction<number>>;
  transcript: Segment[];
  videoRef: React.RefObject<HTMLVideoElement | null>;
}) {
  const handleTimeUpdateCore = useCallback((time: number) => {
    setCurrentTime(time);

    const subtitleIndex = findTranscriptIndexAtTime(transcript, time);
    if (subtitleIndex === -1) {
      return;
    }

    document.getElementById(`sub-${subtitleIndex}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [setCurrentTime, transcript]);

  const throttledTimeUpdate = useThrottledCallback(handleTimeUpdateCore, 100);

  return useCallback(() => {
    if (videoRef.current) {
      throttledTimeUpdate(videoRef.current.currentTime);
    }
  }, [throttledTimeUpdate, videoRef]);
}

function useEditorUploadAction({
  setCurrentJobId,
  setError,
  setLocalSrcWithCleanup,
  setProjectId,
  setTranscript,
  setTranscribing,
  setUploading,
}: {
  setCurrentJobId: React.Dispatch<React.SetStateAction<string | null>>;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  setLocalSrcWithCleanup: (nextSrc: string | null) => void;
  setProjectId: React.Dispatch<React.SetStateAction<string | undefined>>;
  setTranscript: React.Dispatch<React.SetStateAction<Segment[]>>;
  setTranscribing: React.Dispatch<React.SetStateAction<boolean>>;
  setUploading: React.Dispatch<React.SetStateAction<boolean>>;
}) {
  return useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      setError(`Dosya boyutu çok büyük. Maksimum: ${formatUploadLimit(MAX_UPLOAD_BYTES)}`);
      return;
    }

    setLocalSrcWithCleanup(URL.createObjectURL(file));
    setError(null);
    setUploading(true);

    try {
      const response = await clipsApi.upload(file);
      if (response.project_id) {
        setProjectId(response.project_id);
      }

      if (response.status === 'cached' && response.project_id) {
        setTranscript(normalizeTranscript(await editorApi.getTranscript(response.project_id)));
      } else {
        setTranscribing(true);
        setCurrentJobId(response.job_id);
      }
    } catch (error) {
      setError(`Yükleme başarısız: ${getErrorMessage(error, 'Bilinmeyen hata')}`);
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  }, [setCurrentJobId, setError, setLocalSrcWithCleanup, setProjectId, setTranscript, setTranscribing, setUploading]);
}

function useTranscriptUpdateAction(transcript: Segment[]) {
  return useCallback((index: number, text: string) => {
    const nextTranscript = [...transcript];
    nextTranscript[index] = syncSegmentTextAndWords(nextTranscript[index], text);
    return nextTranscript;
  }, [transcript]);
}

function useEditorSaveAction({
  clipProjectId,
  mode,
  projectId,
  setCurrentJobId,
  setError,
  setProcessing,
  setSaving,
  animationType,
  style,
  targetClip,
  transcript,
}: {
  clipProjectId: string | undefined;
  mode: 'master' | 'clip';
  projectId: string | undefined;
  setCurrentJobId: React.Dispatch<React.SetStateAction<string | null>>;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  setProcessing: React.Dispatch<React.SetStateAction<boolean>>;
  setSaving: React.Dispatch<React.SetStateAction<boolean>>;
  animationType: ResolvedEditorSessionState['animationType'];
  style: ResolvedEditorSessionState['style'];
  targetClip?: Clip;
  transcript: Segment[];
}) {
  return useCallback(async () => {
    setSaving(true);
    setError(null);

    try {
      if (mode === 'clip' && targetClip) {
        if (!clipProjectId) {
          throw new Error(tSafe('editorWorkspace.errors.missingProjectContext'));
        }

        const response = await editorApi.reburn({
          animation_type: animationType,
          clip_name: targetClip.name,
          project_id: clipProjectId,
          style_name: style,
          transcript,
        });
        setProcessing(true);
        setCurrentJobId(response.job_id);
      } else {
        await editorApi.saveTranscript(transcript, projectId);
      }
    } catch (error) {
      setError(getErrorMessage(error, tSafe('editorWorkspace.errors.saveFailed')));
    } finally {
      setSaving(false);
    }
  }, [animationType, clipProjectId, mode, projectId, setCurrentJobId, setError, setProcessing, setSaving, style, targetClip, transcript]);
}

function useEditorProcessActions({
  centerX,
  endTime,
  numClips,
  projectId,
  setCurrentJobId,
  setError,
  setProcessing,
  startTime,
  animationType,
  style,
  transcript,
}: {
  centerX: number;
  endTime: number;
  numClips: number;
  projectId: string | undefined;
  setCurrentJobId: React.Dispatch<React.SetStateAction<string | null>>;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  setProcessing: React.Dispatch<React.SetStateAction<boolean>>;
  startTime: number;
  animationType: ResolvedEditorSessionState['animationType'];
  style: ResolvedEditorSessionState['style'];
  transcript: Segment[];
}) {
  const handleProcessBatch = useCallback(async () => {
    const rangeError = getTimeRangeError(startTime, endTime);
    if (rangeError) {
      setError(rangeError);
      return;
    }

    setProcessing(true);
    setError(null);
    try {
      const response = await editorApi.processBatch({
        animation_type: animationType,
        end_time: endTime,
        num_clips: numClips,
        project_id: projectId,
        start_time: startTime,
        style_name: style,
      });
      setCurrentJobId(response.job_id);
    } catch (error) {
      setError(getErrorMessage(error, tSafe('editorWorkspace.errors.batchFailed')));
      setProcessing(false);
    }
  }, [animationType, endTime, numClips, projectId, setCurrentJobId, setError, setProcessing, startTime, style]);

  const handleProcessManual = useCallback(async () => {
    const rangeError = getTimeRangeError(startTime, endTime);
    if (rangeError) {
      setError(rangeError);
      return;
    }

    setProcessing(true);
    setError(null);
    try {
      const response = await editorApi.processManual({
        animation_type: animationType,
        center_x: centerX,
        end_time: endTime,
        project_id: projectId,
        start_time: startTime,
        style_name: style,
        transcript: filterTranscriptForManualRender(transcript, startTime, endTime),
      });
      setCurrentJobId(response.job_id);
    } catch (error) {
      setError(getErrorMessage(error, tSafe('editorWorkspace.errors.manualFailed')));
      setProcessing(false);
    }
  }, [animationType, centerX, endTime, projectId, setCurrentJobId, setError, setProcessing, startTime, style, transcript]);

  return { handleProcessBatch, handleProcessManual };
}

function useEditorDerivedState({
  endTime,
  localSrc,
  mode,
  projectId,
  startTime,
  targetClip,
  transcript,
}: {
  endTime: number;
  localSrc: string | null;
  mode: 'master' | 'clip';
  projectId: string | undefined;
  startTime: number;
  targetClip?: Clip;
  transcript: Segment[];
}) {
  const visibleTranscript = useMemo(
    () => getVisibleTranscriptEntries(transcript, startTime, endTime),
    [endTime, startTime, transcript],
  );
  const videoSrc = useMemo(
    () => resolveEditorVideoSrc(localSrc, mode, targetClip, projectId),
    [localSrc, mode, projectId, targetClip],
  );

  return { videoSrc, visibleTranscript };
}

function useEditorActions({
  clipProjectId,
  mode,
  setLocalSrcWithCleanup,
  state,
  targetClip,
}: {
  clipProjectId: string | undefined;
  mode: 'master' | 'clip';
  setLocalSrcWithCleanup: (nextSrc: string | null) => void;
  state: ReturnType<typeof useEditorState>;
  targetClip?: Clip;
}) {
  const playback = useEditorPlaybackActions({
    endTime: state.endTime,
    setDuration: state.setDuration,
    setEndTime: state.setEndTime,
    startTime: state.startTime,
    videoRef: state.videoRef,
  });
  const handleTimeUpdate = useEditorTimeline({
    setCurrentTime: state.setCurrentTime,
    transcript: state.transcript,
    videoRef: state.videoRef,
  });
  const handleFileUpload = useEditorUploadAction({
    setCurrentJobId: state.setCurrentJobId,
    setError: state.setError,
    setLocalSrcWithCleanup,
    setProjectId: state.setProjectId,
    setTranscript: state.setTranscript,
    setTranscribing: state.setTranscribing,
    setUploading: state.setUploading,
  });
  const updateSubtitleText = useTranscriptUpdateAction(state.transcript);
  const handleSaveTranscript = useEditorSaveAction({
    clipProjectId,
    mode,
    projectId: state.projectId,
    setCurrentJobId: state.setCurrentJobId,
    setError: state.setError,
    setProcessing: state.setProcessing,
    setSaving: state.setSaving,
    animationType: state.animationType,
    style: state.style,
    targetClip,
    transcript: state.transcript,
  });
  const process = useEditorProcessActions({
    centerX: state.centerX,
    endTime: state.endTime,
    numClips: state.numClips,
    projectId: state.projectId,
    setCurrentJobId: state.setCurrentJobId,
    setError: state.setError,
    setProcessing: state.setProcessing,
    startTime: state.startTime,
    animationType: state.animationType,
    style: state.style,
    transcript: state.transcript,
  });

  return { handleFileUpload, handleSaveTranscript, handleTimeUpdate, playback, process, updateSubtitleText };
}

export function useEditorController({ mode = 'master', targetClip }: EditorProps) {
  const { jobs } = useJobStore();
  const clipProjectId = resolveClipProjectId(targetClip);
  const sessionKey = buildEditorSessionKey(mode, targetClip);
  const { localSrc, setLocalSrcWithCleanup } = useLocalPreviewSource();
  const state = useEditorState(clipProjectId);

  useEditorEffects({ clipProjectId, jobs, mode, sessionKey, setLocalSrcWithCleanup, state, targetClip });
  const actions = useEditorActions({ clipProjectId, mode, setLocalSrcWithCleanup, state, targetClip });
  const derived = useEditorDerivedState({
    endTime: state.endTime,
    localSrc,
    mode,
    projectId: state.projectId,
    startTime: state.startTime,
    targetClip,
    transcript: state.transcript,
  });

  return {
    centerX: state.centerX,
    animationType: state.animationType,
    currentTime: state.currentTime,
    duration: state.duration,
    endTime: state.endTime,
    error: state.error,
    fileInputRef: state.fileInputRef,
    handleFileUpload: actions.handleFileUpload,
    handleLoadedMetadata: actions.playback.handleLoadedMetadata,
    handleProcessBatch: actions.process.handleProcessBatch,
    handleProcessManual: actions.process.handleProcessManual,
    handleSaveTranscript: actions.handleSaveTranscript,
    handleTimeUpdate: actions.handleTimeUpdate,
    isPlaying: state.isPlaying,
    jumpToEnd: actions.playback.jumpToEnd,
    jumpToStart: actions.playback.jumpToStart,
    mode,
    numClips: state.numClips,
    processing: state.processing,
    saving: state.saving,
    setCenterX: state.setCenterX,
    setAnimationType: state.setAnimationType,
    setEndTime: state.setEndTime,
    setIsPlaying: state.setIsPlaying,
    setNumClips: state.setNumClips,
    setStartTime: state.setStartTime,
    setStyle: state.setStyle,
    startTime: state.startTime,
    style: state.style,
    togglePlay: actions.playback.togglePlay,
    transcript: state.transcript,
    transcribing: state.transcribing,
    updateSubtitleText: (index: number, text: string) => state.setTranscript(actions.updateSubtitleText(index, text)),
    uploading: state.uploading,
    videoRef: state.videoRef,
    videoSrc: derived.videoSrc,
    visibleTranscript: derived.visibleTranscript,
  };
}

export type EditorController = ReturnType<typeof useEditorController>;
