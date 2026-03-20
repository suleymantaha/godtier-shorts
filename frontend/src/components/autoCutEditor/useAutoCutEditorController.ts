import { useCallback, useMemo } from 'react';

import { API_BASE } from '../../config';
import { useJobStore } from '../../store/useJobStore';
import type { ClipReadyEntry, Job } from '../../types';
import { getQueuePosition, isProjectBusy } from '../../utils/jobQueue';
import { readStored } from '../../utils/storage';
import { getClipUrl } from '../../utils/url';
import { deriveAutoCutJobState } from './helpers';
import { useAutoCutEditorActions } from './useAutoCutEditorActions';
import {
  usePersistAutoCutSession,
  useRevokeLocalVideoUrl,
  useSyncActiveAutoCutJob,
} from './useAutoCutEditorLifecycle';
import { type StoredAutoCutSession, useAutoCutEditorState } from './useAutoCutEditorState';

const AUTO_CUT_SESSION_KEY = 'godtier-auto-cut-session';

function readStoredAutoCutSession() {
  return readStored<StoredAutoCutSession | null>(AUTO_CUT_SESSION_KEY, null);
}

function useCurrentJob(currentJobId: string | null, jobs: Job[]) {
  return useMemo(
    () => (currentJobId ? jobs.find((job) => job.job_id === currentJobId) ?? null : null),
    [currentJobId, jobs],
  );
}

function buildGeneratedClipUrl(clip: Pick<ClipReadyEntry, 'clipName' | 'projectId'>) {
  if (!clip.projectId) {
    return null;
  }

  return `/api/projects/${clip.projectId}/shorts/${clip.clipName}`;
}

function buildGeneratedClips(
  currentJob: Job | null,
  currentJobId: string | null,
  projectId: string | undefined,
  clipReadyByJob: Record<string, ClipReadyEntry[]>,
) {
  if (currentJobId && clipReadyByJob[currentJobId]?.length) {
    return clipReadyByJob[currentJobId];
  }

  if (currentJob?.clip_name) {
    return [{
      at: new Date((currentJob.created_at ?? Date.now() / 1000) * 1000).toISOString(),
      clipName: currentJob.clip_name,
      job_id: currentJob.job_id,
      message: currentJob.last_message,
      progress: currentJob.progress,
      projectId: currentJob.project_id ?? projectId,
      uiTitle: undefined,
    }];
  }

  return [];
}

interface AutoCutControllerOptions {
  onOpenLibrary?: () => void;
}

export function useAutoCutEditorController({ onOpenLibrary }: AutoCutControllerOptions = {}) {
  const initialSession = useMemo(() => readStoredAutoCutSession(), []);
  const { clipReadyByJob, jobs, fetchJobs } = useJobStore();
  const state = useAutoCutEditorState(initialSession);
  const currentJob = useCurrentJob(state.currentJobId, jobs);
  const generatedClips = useMemo(
    () => buildGeneratedClips(currentJob, state.currentJobId, state.projectId, clipReadyByJob),
    [clipReadyByJob, currentJob, state.currentJobId, state.projectId],
  );
  const currentJobMissing = Boolean(state.currentJobId && !currentJob);
  const jobState = useMemo(() => deriveAutoCutJobState({
    currentJob,
    currentJobId: state.currentJobId,
    currentJobMissing,
    isSubmitting: state.isSubmitting,
    pendingOutputUrl: state.pendingOutputUrl,
    requestError: state.requestError,
  }), [currentJob, currentJobMissing, state.currentJobId, state.isSubmitting, state.pendingOutputUrl, state.requestError]);
  const actions = useAutoCutEditorActions({ ...state, fetchJobs });
  const handleOpenLibrary = useCallback(() => {
    onOpenLibrary?.();
  }, [onOpenLibrary]);
  const firstGeneratedClipUrl = useMemo(() => {
    const firstGeneratedClip = generatedClips[0];
    return firstGeneratedClip ? buildGeneratedClipUrl(firstGeneratedClip) : null;
  }, [generatedClips]);
  const resolvedResultUrl = jobState.resultUrl ?? firstGeneratedClipUrl;

  useSyncActiveAutoCutJob({
    currentJobId: state.currentJobId,
    fetchJobs,
    preserveResultOnMissing: Boolean(jobState.resultUrl || generatedClips.length > 0),
    setCurrentJobId: state.setCurrentJobId,
    setPendingOutputUrl: state.setPendingOutputUrl,
    setProjectId: state.setProjectId,
    storageKey: AUTO_CUT_SESSION_KEY,
  });
  usePersistAutoCutSession({
    animationType: state.animationType,
    currentJobId: state.currentJobId,
    endTime: state.endTime,
    layout: state.layout,
    processing: jobState.processing,
    projectId: state.projectId,
    startTime: state.startTime,
    storageKey: AUTO_CUT_SESSION_KEY,
    style: state.style,
  });
  useRevokeLocalVideoUrl(state.localSrc);

  return {
    ...actions,
    ...jobState,
    animationType: state.animationType,
    busy: isProjectBusy(state.projectId, jobs),
    currentJob,
    currentJobId: state.currentJobId,
    cutAsShort: state.cutAsShort,
    duration: state.duration,
    endTime: state.endTime,
    fileInputRef: state.fileInputRef,
    generatedClips,
    handleOpenLibrary,
    isPlaying: state.isPlaying,
    kesFeedback: state.kesFeedback,
    layout: state.layout,
    markers: state.markers,
    numClips: state.numClips,
    projectId: state.projectId,
    queuePosition: state.currentJobId ? getQueuePosition(state.currentJobId, jobs) : null,
    resultVideoSrc: resolvedResultUrl ? getClipUrl({ url: resolvedResultUrl }) : undefined,
    selectedFile: state.selectedFile,
    setAnimationType: state.setAnimationType,
    setCutAsShort: state.setCutAsShort,
    setIsPlaying: state.setIsPlaying,
    setLayout: state.setLayout,
    setSkipSubtitles: state.setSkipSubtitles,
    setStyle: state.setStyle,
    skipSubtitles: state.skipSubtitles,
    startTime: state.startTime,
    style: state.style,
    videoRef: state.videoRef,
    videoSrc: state.localSrc ?? (state.projectId ? `${API_BASE}/api/projects/${state.projectId}/master` : undefined),
  };
}

export type AutoCutEditorController = ReturnType<typeof useAutoCutEditorController>;
