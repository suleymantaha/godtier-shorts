import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react';

import { clipsApi, editorApi } from '../../api/client';
import { useAuthRuntimeStore } from '../../auth/runtime';
import { isStyleName, isSubtitleAnimationType, type StyleName, type SubtitleAnimationType } from '../../config/subtitleStyles';
import { useJobStore } from '../../store/useJobStore';
import type {
  Clip,
  ClipTranscriptCapabilities,
  ClipTranscriptStatus,
  ClipTranscriptResponse,
  Job,
  ProjectTranscriptResponse,
  RenderMetadata,
  Segment,
  TranscriptRecoveryStrategy,
  TranscriptStatus,
} from '../../types';
import { normalizeTranscript } from '../../utils/transcript';
import {
  EMPTY_CLIP_TRANSCRIPT_CAPABILITIES,
  filterSubtitleProjects,
  filterVisibleTranscriptEntries,
  hasSubtitleSelection,
  replaceTranscriptText,
  resolveClipSelectValue,
  resolveCompletionSuccessMessage,
  resolveLoadedEndTime,
  resolveSubtitleVideoSrc,
  resolveTranscriptDuration,
  selectClipByValue,
  type SubtitleEditorMode,
  type SubtitleProject,
} from './helpers';

const CLIP_RECOVERY_JOB_PREFIX = 'cliprecover_';
const CLIP_RECOVERY_SUCCESS_MESSAGE = 'Klip transkripti yüklendi.';
const PROJECT_TRANSCRIPT_JOB_PREFIXES = ['upload_', 'manualcut_', 'projecttranscript_'];
const PROJECT_TRANSCRIPT_SUCCESS_MESSAGE = 'Proje transkripti hazır.';
const REBURN_WARNING_MESSAGE = 'Ham video yok. Videoda zaten gömülü altyazı varsa reburn ikinci kez altyazı basabilir.';

export interface UseSubtitleEditorControllerProps {
  lockedToClip?: boolean;
  targetClip?: Clip | null;
}

function normalizeCapabilities(
  capabilities?: ClipTranscriptCapabilities,
): ClipTranscriptCapabilities {
  return { ...EMPTY_CLIP_TRANSCRIPT_CAPABILITIES, ...capabilities };
}

function isProjectTranscriptJob(jobId: string): boolean {
  return PROJECT_TRANSCRIPT_JOB_PREFIXES.some((prefix) => jobId.startsWith(prefix));
}

function resolveProjectTranscriptStatus(
  response: ProjectTranscriptResponse,
  transcript: Segment[],
): TranscriptStatus {
  if (response.transcript_status) {
    return response.transcript_status;
  }
  return transcript.length > 0 ? 'ready' : 'failed';
}

function resolveClipTranscriptStatus(
  response: ClipTranscriptResponse,
  transcript: Segment[],
): ClipTranscriptStatus {
  if (response.transcript_status) {
    return response.transcript_status;
  }
  return transcript.length > 0 ? 'ready' : 'needs_recovery';
}

function useSubtitleSelectionState() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [mode, setMode] = useState<SubtitleEditorMode>('project');
  const [projects, setProjects] = useState<SubtitleProject[]>([]);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [selectedClip, setSelectedClip] = useState<Clip | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  return {
    clips,
    mode,
    projects,
    projectsError,
    selectedClip,
    selectedProjectId,
    setClips,
    setMode,
    setProjects,
    setProjectsError,
    setSelectedClip,
    setSelectedProjectId,
  };
}

function useSubtitleWorkspaceState() {
  const [cacheBust, setCacheBust] = useState(0);
  const [clipTranscriptCapabilities, setClipTranscriptCapabilities] = useState<ClipTranscriptCapabilities>(
    EMPTY_CLIP_TRANSCRIPT_CAPABILITIES,
  );
  const [clipTranscriptStatus, setClipTranscriptStatus] = useState<ClipTranscriptStatus>('needs_recovery');
  const [clipRenderMetadata, setClipRenderMetadata] = useState<RenderMetadata | null>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [endTime, setEndTime] = useState(60);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [projectTranscriptStatus, setProjectTranscriptStatus] = useState<TranscriptStatus>('ready');
  const [recommendedRecoveryStrategy, setRecommendedRecoveryStrategy] = useState<Exclude<TranscriptRecoveryStrategy, 'auto'> | null>(null);
  const [saving, setSaving] = useState(false);
  const [startTime, setStartTime] = useState(0);
  const [style, setStyle] = useState<StyleName>('HORMOZI');
  const [animationType, setAnimationType] = useState<SubtitleAnimationType>('default');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<Segment[]>([]);
  const videoRef = useRef<HTMLVideoElement>(null);

  return {
    animationType,
    cacheBust,
    clipRenderMetadata,
    clipTranscriptCapabilities,
    clipTranscriptStatus,
    currentJobId,
    currentTime,
    duration,
    endTime,
    error,
    isPlaying,
    loading,
    projectTranscriptStatus,
    recommendedRecoveryStrategy,
    saving,
    setCacheBust,
    setClipRenderMetadata,
    setClipTranscriptCapabilities,
    setClipTranscriptStatus,
    setCurrentJobId,
    setCurrentTime,
    setDuration,
    setEndTime,
    setError,
    setAnimationType,
    setIsPlaying,
    setLoading,
    setProjectTranscriptStatus,
    setRecommendedRecoveryStrategy,
    setSaving,
    setStartTime,
    setStyle,
    setSuccessMessage,
    setTranscript,
    startTime,
    style,
    successMessage,
    transcript,
    videoRef,
  };
}

function useSubtitleSourcesEffect({
  canUseProtectedRequests,
  fetchJobs,
  setClips,
  setProjects,
  setProjectsError,
}: {
  canUseProtectedRequests: boolean;
  fetchJobs: () => Promise<void>;
  setClips: Dispatch<SetStateAction<Clip[]>>;
  setProjects: Dispatch<SetStateAction<SubtitleProject[]>>;
  setProjectsError: Dispatch<SetStateAction<string | null>>;
}) {
  useEffect(() => {
    if (!canUseProtectedRequests) {
      return;
    }

    void fetchJobs();
    editorApi.getProjects().then((response) => {
      setProjects(filterSubtitleProjects(response.projects));
      setProjectsError(response.error ?? null);
    });
    clipsApi.list()
      .then((response) => setClips(response.clips))
      .catch(() => setClips([]));
  }, [canUseProtectedRequests, fetchJobs, setClips, setProjects, setProjectsError]);
}

function useLockedClipSelectionEffect({
  lockedToClip,
  selection,
  targetClip,
}: {
  lockedToClip: boolean;
  selection: ReturnType<typeof useSubtitleSelectionState>;
  targetClip: Clip | null;
}) {
  const wasLockedRef = useRef(lockedToClip);

  useEffect(() => {
    if (lockedToClip && targetClip) {
      selection.setMode('clip');
      selection.setSelectedProjectId(null);
      selection.setSelectedClip(targetClip);
      wasLockedRef.current = true;
      return;
    }

    if (wasLockedRef.current && !lockedToClip) {
      selection.setMode('project');
      selection.setSelectedClip(null);
      selection.setSelectedProjectId(null);
    }

    wasLockedRef.current = lockedToClip;
  }, [
    lockedToClip,
    selection.setMode,
    selection.setSelectedClip,
    selection.setSelectedProjectId,
    targetClip,
  ]);
}

function useTranscriptLoader({
  canUseProtectedRequests,
  fetchJobs,
  mode,
  selectedClip,
  selectedProjectId,
  setAnimationType,
  setClipTranscriptCapabilities,
  setClipTranscriptStatus,
  setClipRenderMetadata,
  setCurrentJobId,
  setDuration,
  setEndTime,
  setError,
  setLoading,
  setProjectTranscriptStatus,
  setRecommendedRecoveryStrategy,
  setStartTime,
  setStyle,
  setTranscript,
}: {
  canUseProtectedRequests: boolean;
  fetchJobs: () => Promise<void>;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
  setAnimationType: Dispatch<SetStateAction<SubtitleAnimationType>>;
  setClipTranscriptCapabilities: Dispatch<SetStateAction<ClipTranscriptCapabilities>>;
  setClipTranscriptStatus: Dispatch<SetStateAction<ClipTranscriptStatus>>;
  setClipRenderMetadata: Dispatch<SetStateAction<RenderMetadata | null>>;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setDuration: Dispatch<SetStateAction<number>>;
  setEndTime: Dispatch<SetStateAction<number>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setLoading: Dispatch<SetStateAction<boolean>>;
  setProjectTranscriptStatus: Dispatch<SetStateAction<TranscriptStatus>>;
  setRecommendedRecoveryStrategy: Dispatch<SetStateAction<Exclude<TranscriptRecoveryStrategy, 'auto'> | null>>;
  setStartTime: Dispatch<SetStateAction<number>>;
  setStyle: Dispatch<SetStateAction<StyleName>>;
  setTranscript: Dispatch<SetStateAction<Segment[]>>;
}) {
  const loadTranscript = useCallback(async () => {
    if (!canUseProtectedRequests) {
      return;
    }

    setError(null);
    setLoading(true);
    try {
      if (mode === 'project' && selectedProjectId) {
        setClipTranscriptCapabilities(EMPTY_CLIP_TRANSCRIPT_CAPABILITIES);
        setClipTranscriptStatus('needs_recovery');
        setClipRenderMetadata(null);
        setRecommendedRecoveryStrategy(null);

        const response = await editorApi.getTranscript(selectedProjectId) as ProjectTranscriptResponse;
        const nextTranscript = normalizeTranscript(response);
        const nextStatus = resolveProjectTranscriptStatus(response, nextTranscript);

        setProjectTranscriptStatus(nextStatus);
        setCurrentJobId(response.active_job_id ?? null);
        setTranscript(nextTranscript);
        setError(nextStatus === 'failed' ? response.last_error ?? null : null);

        if (response.active_job_id) {
          await fetchJobs();
        }
      } else if (mode === 'clip' && selectedClip) {
        if (!selectedClip.project || selectedClip.project === 'legacy') {
          setError('Bu klip icin proje baglami bulunamadi.');
          setLoading(false);
          return;
        }

        const response = await clipsApi.getTranscript(selectedClip.name, selectedClip.project);
        const nextTranscript = normalizeTranscript(response);
        const nextStatus = resolveClipTranscriptStatus(response, nextTranscript);
        const renderMetadata = response.render_metadata;

        setClipTranscriptCapabilities(normalizeCapabilities(response.capabilities));
        setClipTranscriptStatus(nextStatus);
        setClipRenderMetadata(renderMetadata ?? null);
        setProjectTranscriptStatus('ready');
        setRecommendedRecoveryStrategy(response.recommended_strategy ?? null);
        setCurrentJobId(response.active_job_id ?? null);
        setTranscript(nextTranscript);
        if (renderMetadata?.style_name && isStyleName(renderMetadata.style_name)) {
          setStyle(renderMetadata.style_name);
        }
        if (renderMetadata?.animation_type && isSubtitleAnimationType(renderMetadata.animation_type)) {
          setAnimationType(renderMetadata.animation_type);
        }
        setError(nextStatus === 'failed' ? response.last_error ?? null : null);

        if (response.active_job_id) {
          await fetchJobs();
        }
      } else {
        setClipTranscriptCapabilities(EMPTY_CLIP_TRANSCRIPT_CAPABILITIES);
        setClipTranscriptStatus('needs_recovery');
        setClipRenderMetadata(null);
        setCurrentJobId(null);
        setProjectTranscriptStatus('ready');
        setRecommendedRecoveryStrategy(null);
        setTranscript([]);
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Transkript yüklenemedi.');
      setClipTranscriptCapabilities(EMPTY_CLIP_TRANSCRIPT_CAPABILITIES);
      setClipTranscriptStatus('failed');
      setClipRenderMetadata(null);
      setCurrentJobId(null);
      setProjectTranscriptStatus('failed');
      setRecommendedRecoveryStrategy(null);
      setTranscript([]);
    } finally {
      setLoading(false);
    }
  }, [
    canUseProtectedRequests,
    fetchJobs,
    mode,
    selectedClip,
    selectedProjectId,
    setAnimationType,
    setClipTranscriptCapabilities,
    setClipTranscriptStatus,
    setClipRenderMetadata,
    setCurrentJobId,
    setError,
    setLoading,
    setProjectTranscriptStatus,
    setRecommendedRecoveryStrategy,
    setStyle,
    setTranscript,
  ]);

  useEffect(() => {
    if (!canUseProtectedRequests) {
      return;
    }

    if (hasSubtitleSelection(mode, selectedProjectId, selectedClip)) {
      void loadTranscript();
      setStartTime(0);
      setEndTime(60);
      setDuration(0);
      return;
    }

    setClipTranscriptCapabilities(EMPTY_CLIP_TRANSCRIPT_CAPABILITIES);
    setClipTranscriptStatus('needs_recovery');
    setClipRenderMetadata(null);
    setCurrentJobId(null);
    setProjectTranscriptStatus('ready');
    setRecommendedRecoveryStrategy(null);
    setTranscript([]);
  }, [
    canUseProtectedRequests,
    loadTranscript,
    mode,
    selectedClip,
    selectedProjectId,
    setClipTranscriptCapabilities,
    setClipTranscriptStatus,
    setClipRenderMetadata,
    setCurrentJobId,
    setDuration,
    setEndTime,
    setProjectTranscriptStatus,
    setRecommendedRecoveryStrategy,
    setStartTime,
    setTranscript,
  ]);

  return loadTranscript;
}

function useSubtitleJobTrackingEffect({
  currentJob,
  loadTranscript,
  mode,
  selectedClip,
  setCacheBust,
  setCurrentJobId,
  setError,
  setSaving,
  setSuccessMessage,
}: {
  currentJob: Job | null;
  loadTranscript: () => Promise<void>;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  setCacheBust: Dispatch<SetStateAction<number>>;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
}) {
  useEffect(() => {
    if (!currentJob) {
      return;
    }

    const isRecoveryJob = currentJob.job_id.startsWith(CLIP_RECOVERY_JOB_PREFIX);
    const isReburnJob = currentJob.job_id.startsWith('reburn_');
    const isProjectTranscriptRecoveryJob = isProjectTranscriptJob(currentJob.job_id);

    if (currentJob.status === 'completed') {
      setSaving(false);
      setCurrentJobId(null);
      setSuccessMessage(
        isRecoveryJob
          ? CLIP_RECOVERY_SUCCESS_MESSAGE
          : isProjectTranscriptRecoveryJob
            ? PROJECT_TRANSCRIPT_SUCCESS_MESSAGE
            : resolveCompletionSuccessMessage(mode),
      );
      setError(null);

      if (isReburnJob) {
        setCacheBust((value) => value + 1);
      }

      if (isRecoveryJob || isProjectTranscriptRecoveryJob || (mode === 'clip' && selectedClip)) {
        void loadTranscript();
      }
      return;
    }

    if (currentJob.status === 'error' || currentJob.status === 'cancelled') {
      setSaving(false);
      setError(currentJob.error ?? currentJob.last_message ?? 'İşlem başarısız.');
      setCurrentJobId(null);
      if (isRecoveryJob || isProjectTranscriptRecoveryJob) {
        void loadTranscript();
      }
    }
  }, [
    currentJob,
    loadTranscript,
    mode,
    selectedClip,
    setCacheBust,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
  ]);
}

function useSuccessMessageTimeout(
  successMessage: string | null,
  setSuccessMessage: Dispatch<SetStateAction<string | null>>,
) {
  useEffect(() => {
    if (!successMessage) {
      return;
    }

    const timer = window.setTimeout(() => setSuccessMessage(null), 5000);
    return () => window.clearTimeout(timer);
  }, [setSuccessMessage, successMessage]);
}

function useTranscriptDurationEffect({
  duration,
  setDuration,
  setEndTime,
  transcript,
}: {
  duration: number;
  setDuration: Dispatch<SetStateAction<number>>;
  setEndTime: Dispatch<SetStateAction<number>>;
  transcript: Segment[];
}) {
  useEffect(() => {
    if (transcript.length === 0 || duration !== 0) {
      return;
    }

    const nextDuration = resolveTranscriptDuration(transcript);
    setDuration(nextDuration);
    setEndTime(Math.min(60, nextDuration));
  }, [duration, setDuration, setEndTime, transcript]);
}

function useSubtitlePlayback({
  setCurrentTime,
  setDuration,
  setEndTime,
  videoRef,
}: {
  setCurrentTime: Dispatch<SetStateAction<number>>;
  setDuration: Dispatch<SetStateAction<number>>;
  setEndTime: Dispatch<SetStateAction<number>>;
  videoRef: ReturnType<typeof useSubtitleWorkspaceState>['videoRef'];
}) {
  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  }, [setCurrentTime, videoRef]);

  const togglePlay = useCallback(() => {
    if (!videoRef.current) {
      return;
    }

    if (videoRef.current.paused) {
      void videoRef.current.play();
    } else {
      videoRef.current.pause();
    }
  }, [videoRef]);

  const handleLoadedMetadata = useCallback((duration: number) => {
    setDuration(duration);
    setEndTime((previousEndTime) => resolveLoadedEndTime(duration, previousEndTime));
  }, [setDuration, setEndTime]);

  return { handleLoadedMetadata, handleTimeUpdate, togglePlay };
}

function useSubtitleSelectionActions(
  lockedToClip: boolean,
  selection: ReturnType<typeof useSubtitleSelectionState>,
) {
  const selectProjectMode = useCallback(() => {
    if (lockedToClip) {
      return;
    }

    selection.setMode('project');
    selection.setSelectedClip(null);
    selection.setSelectedProjectId(null);
  }, [lockedToClip, selection]);

  const selectClipMode = useCallback(() => {
    if (lockedToClip) {
      return;
    }

    selection.setMode('clip');
    selection.setSelectedProjectId(null);
    selection.setSelectedClip(null);
  }, [lockedToClip, selection]);

  const handleClipSelect = useCallback((value: string) => {
    if (lockedToClip) {
      return;
    }

    selection.setSelectedClip(selectClipByValue(selection.clips, value));
  }, [lockedToClip, selection]);

  return {
    handleClipSelect,
    selectClipMode,
    selectProjectMode,
    setSelectedProjectId: selection.setSelectedProjectId,
  };
}

function useSubtitleEditorActions({
  animationType,
  clipTranscriptCapabilities,
  clipTranscriptStatus,
  endTime,
  fetchJobs,
  mode,
  selectedClip,
  selectedProjectId,
  setAnimationTypeState,
  setCurrentJobId,
  setError,
  setSaving,
  setStyleState,
  setSuccessMessage,
  setTranscript,
  startTime,
  style,
  transcript,
}: {
  animationType: SubtitleAnimationType;
  clipTranscriptCapabilities: ClipTranscriptCapabilities;
  clipTranscriptStatus: ClipTranscriptStatus;
  endTime: number;
  fetchJobs: () => Promise<void>;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
  setAnimationTypeState: Dispatch<SetStateAction<SubtitleAnimationType>>;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setStyleState: Dispatch<SetStateAction<StyleName>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
  setTranscript: Dispatch<SetStateAction<Segment[]>>;
  startTime: number;
  style: StyleName;
  transcript: Segment[];
}) {
  const updateSubtitleText = useCallback((index: number, text: string) => {
    setTranscript((currentTranscript) => replaceTranscriptText(currentTranscript, index, text));
  }, [setTranscript]);

  const handleSave = useSubtitleSaveAction({
    animationType,
    clipTranscriptCapabilities,
    fetchJobs,
    mode,
    selectedClip,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
    style,
    transcript,
  });
  const handleRecoverProjectTranscript = useProjectTranscriptRecoveryAction({
    fetchJobs,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
  });
  const handleRenderClip = useSubtitleRenderAction({
    animationType,
    endTime,
    fetchJobs,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
    startTime,
    style,
    transcript,
  });
  const handleRecoverTranscript = useSubtitleRecoveryAction({
    clipTranscriptCapabilities,
    clipTranscriptStatus,
    fetchJobs,
    selectedClip,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
  });
  const setStyle = useCallback((value: string) => {
    setStyleState(isStyleName(value) ? value : 'HORMOZI');
  }, [setStyleState]);
  const setAnimationType = useCallback((value: string) => {
    setAnimationTypeState(isSubtitleAnimationType(value) ? value : 'default');
  }, [setAnimationTypeState]);

  return {
    handleRecoverProjectTranscript,
    handleRecoverTranscript,
    handleRenderClip,
    handleSave,
    setAnimationType,
    setStyle,
    updateSubtitleText,
  };
}

function useSubtitleSaveAction({
  animationType,
  clipTranscriptCapabilities,
  fetchJobs,
  mode,
  selectedClip,
  selectedProjectId,
  setCurrentJobId,
  setError,
  setSaving,
  setSuccessMessage,
  style,
  transcript,
}: {
  animationType: SubtitleAnimationType;
  clipTranscriptCapabilities: ClipTranscriptCapabilities;
  fetchJobs: () => Promise<void>;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
  style: StyleName;
  transcript: Segment[];
}) {
  return useCallback(async () => {
    setError(null);
    setSuccessMessage(null);
    setSaving(true);
    try {
      if (mode === 'project' && selectedProjectId) {
        await editorApi.saveTranscript(transcript, selectedProjectId);
        setSuccessMessage('Transcript kaydedildi.');
        setSaving(false);
        return;
      }

      if (mode === 'clip' && selectedClip) {
        if (!selectedClip.project || selectedClip.project === 'legacy') {
          setError('Bu klip icin proje baglami bulunamadi.');
          setSaving(false);
          return;
        }

        if (
          !clipTranscriptCapabilities.has_raw_backup
          && typeof window !== 'undefined'
          && !window.confirm(`${REBURN_WARNING_MESSAGE}\n\nDevam etmek istiyor musunuz?`)
        ) {
          setSaving(false);
          return;
        }
        const response = await editorApi.reburn({
          animation_type: animationType,
          clip_name: selectedClip.name,
          project_id: selectedClip.project,
          style_name: style,
          transcript,
        });
        setCurrentJobId(response.job_id ?? null);
        await fetchJobs();
        return;
      }

      setSaving(false);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Kaydetme başarısız.');
      setSaving(false);
    }
  }, [
    animationType,
    clipTranscriptCapabilities.has_raw_backup,
    fetchJobs,
    mode,
    selectedClip,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
    style,
    transcript,
  ]);
}

function useProjectTranscriptRecoveryAction({
  fetchJobs,
  selectedProjectId,
  setCurrentJobId,
  setError,
  setSaving,
  setSuccessMessage,
}: {
  fetchJobs: () => Promise<void>;
  selectedProjectId: string | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
}) {
  return useCallback(async () => {
    if (!selectedProjectId) {
      return;
    }

    setError(null);
    setSuccessMessage(null);
    setSaving(true);

    try {
      const response = await editorApi.recoverProjectTranscript({ project_id: selectedProjectId });
      setCurrentJobId(response.job_id ?? null);
      if (response.job_id) {
        await fetchJobs();
        return;
      }
      setSaving(false);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Proje transkripti yeniden çıkarılamadı.');
      setSaving(false);
    }
  }, [
    fetchJobs,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
  ]);
}

function useSubtitleRecoveryAction({
  clipTranscriptCapabilities,
  clipTranscriptStatus,
  fetchJobs,
  selectedClip,
  setCurrentJobId,
  setError,
  setSaving,
  setSuccessMessage,
}: {
  clipTranscriptCapabilities: ClipTranscriptCapabilities;
  clipTranscriptStatus: ClipTranscriptStatus;
  fetchJobs: () => Promise<void>;
  selectedClip: Clip | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
}) {
  return useCallback(async (strategy: TranscriptRecoveryStrategy) => {
    if (!selectedClip) {
      return;
    }

    if (strategy === 'project_slice' && !clipTranscriptCapabilities.can_recover_from_project) {
      return;
    }
    if (strategy === 'transcribe_source' && !clipTranscriptCapabilities.can_transcribe_source) {
      return;
    }
    if (strategy === 'auto' && clipTranscriptStatus !== 'needs_recovery' && clipTranscriptStatus !== 'failed') {
      return;
    }

    setError(null);
    setSuccessMessage(null);
    setSaving(true);

    try {
      const projectId = clipTranscriptCapabilities.resolved_project_id
        ?? (selectedClip.project && selectedClip.project !== 'legacy' ? selectedClip.project : undefined);
      if (!projectId) {
        throw new Error('Bu klip icin proje baglami bulunamadi.');
      }

      const response = await editorApi.recoverClipTranscript({
        clip_name: selectedClip.name,
        project_id: projectId,
        strategy,
      });
      setCurrentJobId(response.job_id ?? null);
      if (response.job_id) {
        await fetchJobs();
        return;
      }
      setSaving(false);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Klip transkripti kurtarılamadı.');
      setSaving(false);
    }
  }, [
    clipTranscriptCapabilities.can_recover_from_project,
    clipTranscriptCapabilities.can_transcribe_source,
    clipTranscriptCapabilities.resolved_project_id,
    clipTranscriptStatus,
    fetchJobs,
    selectedClip,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
  ]);
}

function useSubtitleRenderAction({
  animationType,
  endTime,
  fetchJobs,
  selectedProjectId,
  setCurrentJobId,
  setError,
  setSaving,
  setSuccessMessage,
  startTime,
  style,
  transcript,
}: {
  animationType: SubtitleAnimationType;
  endTime: number;
  fetchJobs: () => Promise<void>;
  selectedProjectId: string | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
  startTime: number;
  style: StyleName;
  transcript: Segment[];
}) {
  return useCallback(async () => {
    if (!selectedProjectId || endTime <= startTime) {
      return;
    }

    setError(null);
    setSuccessMessage(null);
    setSaving(true);
    try {
      const response = await editorApi.processManual({
        animation_type: animationType,
        end_time: endTime,
        project_id: selectedProjectId,
        start_time: startTime,
        style_name: style,
        transcript,
      });
      setCurrentJobId(response.job_id);
      await fetchJobs();
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Klip üretilemedi.');
      setSaving(false);
    }
  }, [
    animationType,
    endTime,
    fetchJobs,
    selectedProjectId,
    setCurrentJobId,
    setError,
    setSaving,
    setSuccessMessage,
    startTime,
    style,
    transcript,
  ]);
}

function useActiveJobSyncEffect({
  currentJob,
  currentJobId,
  fetchJobs,
}: {
  currentJob: Job | null;
  currentJobId: string | null;
  fetchJobs: () => Promise<void>;
}) {
  useEffect(() => {
    if (!currentJobId || currentJob) {
      return;
    }
    void fetchJobs();
  }, [currentJob, currentJobId, fetchJobs]);
}

function useClipAutoRecoveryEffect({
  clipTranscriptStatus,
  currentJobId,
  handleRecoverTranscript,
  loading,
  mode,
  recommendedRecoveryStrategy,
  selectedClip,
  transcript,
}: {
  clipTranscriptStatus: ClipTranscriptStatus;
  currentJobId: string | null;
  handleRecoverTranscript: (strategy: TranscriptRecoveryStrategy) => Promise<void>;
  loading: boolean;
  mode: SubtitleEditorMode;
  recommendedRecoveryStrategy: Exclude<TranscriptRecoveryStrategy, 'auto'> | null;
  selectedClip: Clip | null;
  transcript: Segment[];
}) {
  const attemptedKeysRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (
      mode !== 'clip'
      || !selectedClip
      || loading
      || transcript.length > 0
      || currentJobId
      || (clipTranscriptStatus !== 'needs_recovery' && clipTranscriptStatus !== 'failed')
      || !recommendedRecoveryStrategy
    ) {
      return;
    }

    const clipKey = `${selectedClip.project ?? 'legacy'}:${selectedClip.name}`;
    if (attemptedKeysRef.current.has(clipKey)) {
      return;
    }

    attemptedKeysRef.current.add(clipKey);
    void handleRecoverTranscript('auto');
  }, [
    clipTranscriptStatus,
    currentJobId,
    handleRecoverTranscript,
    loading,
    mode,
    recommendedRecoveryStrategy,
    selectedClip,
    transcript,
  ]);
}

function buildSubtitleEditorController({
  currentTime,
  currentJob,
  currentVideoState,
  editorActions,
  hasSelection,
  lockedToClip,
  playback,
  selection,
  selectionActions,
  visibleTranscriptEntries,
  workspace,
}: {
  currentTime: number;
  currentJob: Job | null;
  currentVideoState: {
    isPlaying: boolean;
    videoRef: ReturnType<typeof useSubtitleWorkspaceState>['videoRef'];
    videoSrc: string | undefined;
  };
  editorActions: ReturnType<typeof useSubtitleEditorActions>;
  hasSelection: boolean;
  lockedToClip: boolean;
  playback: ReturnType<typeof useSubtitlePlayback>;
  selection: ReturnType<typeof useSubtitleSelectionState>;
  selectionActions: ReturnType<typeof useSubtitleSelectionActions>;
  visibleTranscriptEntries: ReturnType<typeof filterVisibleTranscriptEntries>;
  workspace: ReturnType<typeof useSubtitleWorkspaceState>;
}) {
  return {
    animationType: workspace.animationType,
    clipTranscriptCapabilities: workspace.clipTranscriptCapabilities,
    clipTranscriptStatus: workspace.clipTranscriptStatus,
    clipRenderMetadata: workspace.clipRenderMetadata,
    clips: selection.clips,
    currentJob,
    currentTime,
    duration: workspace.duration,
    endTime: workspace.endTime,
    error: workspace.error,
    handleClipSelect: selectionActions.handleClipSelect,
    handleLoadedMetadata: playback.handleLoadedMetadata,
    handleRecoverProjectTranscript: editorActions.handleRecoverProjectTranscript,
    handleRecoverTranscript: editorActions.handleRecoverTranscript,
    handleRenderClip: editorActions.handleRenderClip,
    handleSave: editorActions.handleSave,
    handleTimeUpdate: playback.handleTimeUpdate,
    hasSelection,
    isPlaying: currentVideoState.isPlaying,
    loading: workspace.loading,
    lockedToClip,
    mode: selection.mode,
    projects: selection.projects,
    projectsError: selection.projectsError,
    projectTranscriptStatus: workspace.projectTranscriptStatus,
    reburnWarningMessage: REBURN_WARNING_MESSAGE,
    recommendedRecoveryStrategy: workspace.recommendedRecoveryStrategy,
    resolveClipSelectValue,
    saving: workspace.saving,
    selectClipMode: selectionActions.selectClipMode,
    selectProjectMode: selectionActions.selectProjectMode,
    selectedClip: selection.selectedClip,
    selectedProjectId: selection.selectedProjectId,
    setCurrentTime: workspace.setCurrentTime,
    setEndTime: workspace.setEndTime,
    setIsPlaying: workspace.setIsPlaying,
    setSelectedProjectId: selectionActions.setSelectedProjectId,
    setStartTime: workspace.setStartTime,
    setAnimationType: editorActions.setAnimationType,
    setStyle: editorActions.setStyle,
    startTime: workspace.startTime,
    style: workspace.style,
    successMessage: workspace.successMessage,
    togglePlay: playback.togglePlay,
    transcript: workspace.transcript,
    updateSubtitleText: editorActions.updateSubtitleText,
    videoRef: currentVideoState.videoRef,
    videoSrc: currentVideoState.videoSrc,
    visibleTranscriptEntries,
  };
}

function useSubtitleControllerServices({
  canUseProtectedRequests,
  fetchJobs,
  jobs,
  lockedToClip,
  selection,
  workspace,
}: {
  canUseProtectedRequests: boolean;
  fetchJobs: () => Promise<void>;
  jobs: Job[];
  lockedToClip: boolean;
  selection: ReturnType<typeof useSubtitleSelectionState>;
  workspace: ReturnType<typeof useSubtitleWorkspaceState>;
}) {
  const currentJob = useMemo(
    () => workspace.currentJobId ? jobs.find((job) => job.job_id === workspace.currentJobId) ?? null : null,
    [jobs, workspace.currentJobId],
  );
  const hasSelection = hasSubtitleSelection(selection.mode, selection.selectedProjectId, selection.selectedClip);
  const loadTranscript = useTranscriptLoader({
    canUseProtectedRequests,
    fetchJobs,
    mode: selection.mode,
    selectedClip: selection.selectedClip,
    selectedProjectId: selection.selectedProjectId,
    setAnimationType: workspace.setAnimationType,
    setClipTranscriptCapabilities: workspace.setClipTranscriptCapabilities,
    setClipTranscriptStatus: workspace.setClipTranscriptStatus,
    setClipRenderMetadata: workspace.setClipRenderMetadata,
    setCurrentJobId: workspace.setCurrentJobId,
    setDuration: workspace.setDuration,
    setEndTime: workspace.setEndTime,
    setError: workspace.setError,
    setLoading: workspace.setLoading,
    setProjectTranscriptStatus: workspace.setProjectTranscriptStatus,
    setRecommendedRecoveryStrategy: workspace.setRecommendedRecoveryStrategy,
    setStartTime: workspace.setStartTime,
    setStyle: workspace.setStyle,
    setTranscript: workspace.setTranscript,
  });
  const playback = useSubtitlePlayback({
    setCurrentTime: workspace.setCurrentTime,
    setDuration: workspace.setDuration,
    setEndTime: workspace.setEndTime,
    videoRef: workspace.videoRef,
  });
  const selectionActions = useSubtitleSelectionActions(lockedToClip, selection);
  const editorActions = useSubtitleEditorActions({
    animationType: workspace.animationType,
    clipTranscriptCapabilities: workspace.clipTranscriptCapabilities,
    clipTranscriptStatus: workspace.clipTranscriptStatus,
    endTime: workspace.endTime,
    fetchJobs,
    mode: selection.mode,
    selectedClip: selection.selectedClip,
    selectedProjectId: selection.selectedProjectId,
    setAnimationTypeState: workspace.setAnimationType,
    setCurrentJobId: workspace.setCurrentJobId,
    setError: workspace.setError,
    setSaving: workspace.setSaving,
    setStyleState: workspace.setStyle,
    setSuccessMessage: workspace.setSuccessMessage,
    setTranscript: workspace.setTranscript,
    startTime: workspace.startTime,
    style: workspace.style,
    transcript: workspace.transcript,
  });
  const videoState = {
    isPlaying: workspace.isPlaying,
    videoRef: workspace.videoRef,
    videoSrc: resolveSubtitleVideoSrc({
      cacheBust: workspace.cacheBust,
      mode: selection.mode,
      selectedClip: selection.selectedClip,
      selectedProjectId: selection.selectedProjectId,
    }),
  };
  const visibleTranscriptEntries = filterVisibleTranscriptEntries(
    workspace.transcript,
    workspace.startTime,
    workspace.endTime,
  );

  return {
    currentJob,
    editorActions,
    hasSelection,
    loadTranscript,
    playback,
    selectionActions,
    videoState,
    visibleTranscriptEntries,
  };
}

export function useSubtitleEditorController({
  lockedToClip = false,
  targetClip = null,
}: UseSubtitleEditorControllerProps = {}) {
  const canUseProtectedRequests = useAuthRuntimeStore((state) => state.canUseProtectedRequests);
  const { fetchJobs, jobs } = useJobStore();
  const selection = useSubtitleSelectionState();
  const workspace = useSubtitleWorkspaceState();
  const services = useSubtitleControllerServices({
    canUseProtectedRequests,
    fetchJobs,
    jobs,
    lockedToClip,
    selection,
    workspace,
  });

  useSubtitleSourcesEffect({
    canUseProtectedRequests,
    fetchJobs,
    setClips: selection.setClips,
    setProjects: selection.setProjects,
    setProjectsError: selection.setProjectsError,
  });
  useLockedClipSelectionEffect({ lockedToClip, selection, targetClip });
  useSubtitleJobTrackingEffect({
    currentJob: services.currentJob,
    loadTranscript: services.loadTranscript,
    mode: selection.mode,
    selectedClip: selection.selectedClip,
    setCacheBust: workspace.setCacheBust,
    setCurrentJobId: workspace.setCurrentJobId,
    setError: workspace.setError,
    setSaving: workspace.setSaving,
    setSuccessMessage: workspace.setSuccessMessage,
  });
  useActiveJobSyncEffect({
    currentJob: services.currentJob,
    currentJobId: workspace.currentJobId,
    fetchJobs,
  });
  useClipAutoRecoveryEffect({
    clipTranscriptStatus: workspace.clipTranscriptStatus,
    currentJobId: workspace.currentJobId,
    handleRecoverTranscript: services.editorActions.handleRecoverTranscript,
    loading: workspace.loading,
    mode: selection.mode,
    recommendedRecoveryStrategy: workspace.recommendedRecoveryStrategy,
    selectedClip: selection.selectedClip,
    transcript: workspace.transcript,
  });
  useSuccessMessageTimeout(workspace.successMessage, workspace.setSuccessMessage);
  useTranscriptDurationEffect({
    duration: workspace.duration,
    setDuration: workspace.setDuration,
    setEndTime: workspace.setEndTime,
    transcript: workspace.transcript,
  });

  return buildSubtitleEditorController({
    currentTime: workspace.currentTime,
    currentJob: services.currentJob,
    currentVideoState: services.videoState,
    editorActions: services.editorActions,
    hasSelection: services.hasSelection,
    lockedToClip,
    playback: services.playback,
    selection,
    selectionActions: services.selectionActions,
    visibleTranscriptEntries: services.visibleTranscriptEntries,
    workspace,
  });
}

export type SubtitleEditorController = ReturnType<typeof useSubtitleEditorController>;
