import { useMemo } from 'react';

import { API_BASE } from '../../config';
import { useJobStore } from '../../store/useJobStore';
import type { Job } from '../../types';
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

export function useAutoCutEditorController() {
  const initialSession = useMemo(() => readStoredAutoCutSession(), []);
  const { jobs, fetchJobs } = useJobStore();
  const state = useAutoCutEditorState(initialSession);
  const currentJob = useCurrentJob(state.currentJobId, jobs);
  const jobState = useMemo(() => deriveAutoCutJobState({
    currentJob,
    currentJobId: state.currentJobId,
    isSubmitting: state.isSubmitting,
    pendingOutputUrl: state.pendingOutputUrl,
    requestError: state.requestError,
  }), [currentJob, state.currentJobId, state.isSubmitting, state.pendingOutputUrl, state.requestError]);
  const actions = useAutoCutEditorActions({ ...state, fetchJobs });

  useSyncActiveAutoCutJob({
    currentJobId: state.currentJobId,
    fetchJobs,
    setCurrentJobId: state.setCurrentJobId,
    setPendingOutputUrl: state.setPendingOutputUrl,
    setProjectId: state.setProjectId,
    storageKey: AUTO_CUT_SESSION_KEY,
  });
  usePersistAutoCutSession({
    animationType: state.animationType,
    currentJobId: state.currentJobId,
    endTime: state.endTime,
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
    isPlaying: state.isPlaying,
    kesFeedback: state.kesFeedback,
    markers: state.markers,
    numClips: state.numClips,
    projectId: state.projectId,
    queuePosition: state.currentJobId ? getQueuePosition(state.currentJobId, jobs) : null,
    resultVideoSrc: jobState.resultUrl ? getClipUrl({ url: jobState.resultUrl }) : undefined,
    selectedFile: state.selectedFile,
    setAnimationType: state.setAnimationType,
    setCutAsShort: state.setCutAsShort,
    setIsPlaying: state.setIsPlaying,
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
