import { useEffect, useRef, type Dispatch, type SetStateAction } from 'react';

import {
  clearSubtitleSessionSnapshot,
  persistSubtitleSessionSnapshot,
  readSubtitleSessionSnapshot,
  type SubtitleSessionJobKind,
} from '../../app/helpers';
import { tSafe } from '../../i18n';
import type {
  Clip,
  ClipTranscriptStatus,
  Job,
  Segment,
  TranscriptRecoveryStrategy,
} from '../../types';
import { resolveCompletionSuccessMessage, type SubtitleEditorMode } from './helpers';
import {
  CLIP_RECOVERY_JOB_PREFIX,
  getClipRecoverySuccessMessage,
  getProjectTranscriptSuccessMessage,
  isProjectTranscriptJob,
  type TranscriptAccessState,
} from './shared';
import type { TranscriptLoadOptions } from './useSubtitleEditorController';
import { resolveClipProjectId } from './transcriptLoader';

export function resolveSubtitleSessionJobKind(jobId: string | null): SubtitleSessionJobKind {
  if (!jobId) {
    return 'unknown';
  }
  if (jobId.startsWith('reburn_')) {
    return 'reburn';
  }
  if (jobId.startsWith(CLIP_RECOVERY_JOB_PREFIX)) {
    return 'clip_recovery';
  }
  if (isProjectTranscriptJob(jobId)) {
    return 'project_transcript';
  }
  if (jobId.startsWith('manual_')) {
    return 'range_render';
  }
  return 'unknown';
}

export function isActiveTrackedJob(job: Job): boolean {
  return job.status === 'queued' || job.status === 'processing';
}

function matchesSubtitleSelectionJob({
  job,
  mode,
  selectedClip,
  selectedProjectId,
}: {
  job: Job;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
}) {
  if (mode === 'project') {
    if (!selectedProjectId || job.project_id !== selectedProjectId) {
      return false;
    }

    const jobKind = resolveSubtitleSessionJobKind(job.job_id);
    return jobKind === 'project_transcript' || jobKind === 'range_render';
  }

  const projectId = resolveClipProjectId(selectedClip);
  if (!selectedClip || !projectId || job.project_id !== projectId) {
    return false;
  }

  return job.url === selectedClip.name || job.clip_name === selectedClip.name;
}

function findMatchingSubtitleJob({
  jobs,
  mode,
  preferredJobId,
  selectedClip,
  selectedProjectId,
}: {
  jobs: Job[];
  mode: SubtitleEditorMode;
  preferredJobId: string | null;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
}) {
  if (preferredJobId) {
    const exactMatch = jobs.find((job) => job.job_id === preferredJobId);
    if (exactMatch) {
      return exactMatch;
    }
  }

  const activeMatch = jobs.find((job) => (
    isActiveTrackedJob(job)
    && matchesSubtitleSelectionJob({ job, mode, selectedClip, selectedProjectId })
  ));
  if (activeMatch) {
    return activeMatch;
  }

  return jobs.find((job) => matchesSubtitleSelectionJob({
    job,
    mode,
    selectedClip,
    selectedProjectId,
  })) ?? null;
}

function resolveJobTrackingFlags(currentJob: Job) {
  return {
    isProjectTranscriptRecoveryJob: isProjectTranscriptJob(currentJob.job_id),
    isRangeRenderJob: currentJob.job_id.startsWith('manual_'),
    isReburnJob: currentJob.job_id.startsWith('reburn_'),
    isRecoveryJob: currentJob.job_id.startsWith(CLIP_RECOVERY_JOB_PREFIX),
  };
}

function shouldReloadTranscriptAfterCompletion({
  isProjectTranscriptRecoveryJob,
  isRangeRenderJob,
  isRecoveryJob,
  mode,
  selectedClip,
}: {
  isProjectTranscriptRecoveryJob: boolean;
  isRangeRenderJob: boolean;
  isRecoveryJob: boolean;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
}) {
  return (
    isRecoveryJob
    || isProjectTranscriptRecoveryJob
    || isRangeRenderJob
    || (mode === 'clip' && selectedClip)
  );
}

function resolveJobSuccessMessage({
  isProjectTranscriptRecoveryJob,
  isRecoveryJob,
  mode,
}: {
  isProjectTranscriptRecoveryJob: boolean;
  isRecoveryJob: boolean;
  mode: SubtitleEditorMode;
}) {
  if (isRecoveryJob) {
    return getClipRecoverySuccessMessage();
  }
  if (isProjectTranscriptRecoveryJob) {
    return getProjectTranscriptSuccessMessage();
  }
  return resolveCompletionSuccessMessage(mode);
}

export function useSubtitleJobTrackingEffect({
  currentJob,
  fetchJobs,
  loadTranscript,
  mode,
  selectedClip,
  selectionKey,
  setCacheBust,
  setError,
  setSaving,
  setSuccessMessage,
}: {
  currentJob: Job | null;
  fetchJobs: () => Promise<void>;
  loadTranscript: (options?: TranscriptLoadOptions) => Promise<void>;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  selectionKey: string | null;
  setCacheBust: Dispatch<SetStateAction<number>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSuccessMessage: Dispatch<SetStateAction<string | null>>;
}) {
  const handledTerminalJobRef = useRef<string | null>(null);

  useEffect(() => {
    if (!currentJob) {
      handledTerminalJobRef.current = null;
      return;
    }

    const flags = resolveJobTrackingFlags(currentJob);
    const isTerminal = currentJob.status === 'completed' || currentJob.status === 'error' || currentJob.status === 'cancelled';
    const terminalKey = isTerminal ? `${currentJob.job_id}:${currentJob.status}` : null;

    if (!isTerminal) {
      handledTerminalJobRef.current = null;
      return;
    }

    if (terminalKey && handledTerminalJobRef.current === terminalKey) {
      return;
    }

    handledTerminalJobRef.current = terminalKey;

    if (currentJob.status === 'completed') {
      setSaving(false);
      setSuccessMessage(resolveJobSuccessMessage({ ...flags, mode }));
      setError(null);
      if (selectionKey) {
        clearSubtitleSessionSnapshot();
      }

      if (flags.isReburnJob) {
        setCacheBust((value) => value + 1);
      }

      if (shouldReloadTranscriptAfterCompletion({ ...flags, mode, selectedClip })) {
        void loadTranscript();
      }
      void fetchJobs();
      return;
    }

    if (currentJob.status === 'error' || currentJob.status === 'cancelled') {
      setSaving(false);
      setError(currentJob.error ?? currentJob.last_message ?? tSafe('subtitleEditor.transcript.processingFailed'));
      if (selectionKey) {
        clearSubtitleSessionSnapshot();
      }
      if (flags.isRecoveryJob || flags.isProjectTranscriptRecoveryJob) {
        void loadTranscript();
      }
      void fetchJobs();
    }
  }, [
    currentJob,
    fetchJobs,
    loadTranscript,
    mode,
    selectedClip,
    selectionKey,
    setCacheBust,
    setError,
    setSaving,
    setSuccessMessage,
  ]);
}

export function useActiveJobSyncEffect({
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

export function usePersistedSubtitleSessionEffect({
  currentJob,
  currentJobId,
  mode,
  selectedClip,
  selectedProjectId,
  selectionKey,
}: {
  currentJob: Job | null;
  currentJobId: string | null;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
  selectionKey: string | null;
}) {
  useEffect(() => {
    if (!selectionKey || !currentJobId) {
      return;
    }

    if (currentJob && !isActiveTrackedJob(currentJob)) {
      return;
    }

    persistSubtitleSessionSnapshot({
      clipName: mode === 'clip' ? selectedClip?.name ?? null : null,
      currentJobId,
      jobKind: resolveSubtitleSessionJobKind(currentJob?.job_id ?? currentJobId),
      mode,
      projectId: mode === 'project' ? selectedProjectId : resolveClipProjectId(selectedClip),
      selectionKey,
      startedAt: currentJob ? currentJob.created_at * 1000 : Date.now(),
    });
  }, [currentJob, currentJobId, mode, selectedClip, selectedProjectId, selectionKey]);
}

export function usePersistedSubtitleSessionResumeEffect({
  currentJobId,
  fetchJobs,
  jobs,
  mode,
  selectedClip,
  selectedProjectId,
  selectionKey,
  setCurrentJobId,
}: {
  currentJobId: string | null;
  fetchJobs: () => Promise<void>;
  jobs: Job[];
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
  selectionKey: string | null;
  setCurrentJobId: Dispatch<SetStateAction<string | null>>;
}) {
  useEffect(() => {
    if (!selectionKey || currentJobId) {
      return;
    }

    const snapshot = readSubtitleSessionSnapshot();
    const preferredJobId = snapshot?.selectionKey === selectionKey ? snapshot.currentJobId : null;
    const matchedJob = findMatchingSubtitleJob({
      jobs,
      mode,
      preferredJobId,
      selectedClip,
      selectedProjectId,
    });

    if (matchedJob) {
      setCurrentJobId(matchedJob.job_id);
      return;
    }

    if (preferredJobId) {
      setCurrentJobId(preferredJobId);
      void fetchJobs();
    }
  }, [currentJobId, fetchJobs, jobs, mode, selectedClip, selectedProjectId, selectionKey, setCurrentJobId]);
}

export function useClipAutoRecoveryEffect({
  clipTranscriptStatus,
  currentJobId,
  handleRecoverTranscript,
  loading,
  mode,
  recommendedRecoveryStrategy,
  selectedClip,
  transcriptAccessState,
  transcript,
}: {
  clipTranscriptStatus: ClipTranscriptStatus;
  currentJobId: string | null;
  handleRecoverTranscript: (strategy: TranscriptRecoveryStrategy) => Promise<void>;
  loading: boolean;
  mode: SubtitleEditorMode;
  recommendedRecoveryStrategy: Exclude<TranscriptRecoveryStrategy, 'auto'> | null;
  selectedClip: Clip | null;
  transcriptAccessState: TranscriptAccessState;
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
      || transcriptAccessState !== 'ready'
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
    transcriptAccessState,
    transcript,
  ]);
}
