import { useCallback, useEffect, useRef, type Dispatch, type SetStateAction } from 'react';

import { clipsApi, editorApi } from '../../api/client';
import type { AppErrorCode } from '../../api/errors';
import { tSafe } from '../../i18n';
import type { Clip } from '../../types';
import type { SubtitleSelectionState } from './useSubtitleEditorController';
import {
  filterSubtitleProjects,
  hasSameLockedClipContext,
  reconcileLockedClip,
  type SubtitleProject,
} from './helpers';
import { AUTH_BOOTSTRAP_RECOVERY_MS, type ProjectsFetchStatus, type SubtitleSourceState } from './shared';

function resolveSubtitleSourceBlockedMessage(pauseReason: AppErrorCode | null): string {
  if (pauseReason === 'token_expired') {
    return tSafe('subtitleEditor.selection.blocked.tokenExpired');
  }
  if (pauseReason === 'unauthorized') {
    return tSafe('subtitleEditor.selection.blocked.unauthorized');
  }
  if (pauseReason === 'forbidden') {
    return tSafe('subtitleEditor.selection.blocked.forbidden');
  }
  if (pauseReason === 'network_offline' || pauseReason === 'auth_revalidation_required') {
    return tSafe('subtitleEditor.selection.blocked.networkOffline');
  }
  return tSafe('subtitleEditor.selection.blocked.fallback');
}

export function useSubtitleSourcesEffect({
  canUseProtectedRequests,
  fetchJobs,
  pauseReason,
  sourceState,
  setClips,
  setProjects,
  setProjectsError,
  setProjectsStatus,
  setSourceMessage,
  setSourceState,
}: {
  canUseProtectedRequests: boolean;
  fetchJobs: () => Promise<void>;
  pauseReason: AppErrorCode | null;
  sourceState: SubtitleSourceState;
  setClips: Dispatch<SetStateAction<Clip[]>>;
  setProjects: Dispatch<SetStateAction<SubtitleProject[]>>;
  setProjectsError: Dispatch<SetStateAction<string | null>>;
  setProjectsStatus: Dispatch<SetStateAction<ProjectsFetchStatus>>;
  setSourceMessage: Dispatch<SetStateAction<string | null>>;
  setSourceState: Dispatch<SetStateAction<SubtitleSourceState>>;
}) {
  const loadSources = useCallback(async (options?: { forceAuthRecovery?: boolean }) => {
    if (!canUseProtectedRequests && !options?.forceAuthRecovery) {
      return;
    }

    setSourceState('loading');
    setSourceMessage(null);

    void fetchJobs();
    const [projectsResponse, clipsResponse] = await Promise.all([
      editorApi.getProjects(),
      clipsApi.list().catch(() => ({ clips: [] })),
    ]);

    if (projectsResponse) {
      setProjects(filterSubtitleProjects(projectsResponse.projects));
      setProjectsError(projectsResponse.error);
      setProjectsStatus(projectsResponse.status);
    }

    if (clipsResponse) {
      setClips(clipsResponse.clips);
    }

    setSourceState('ready');
  }, [
    canUseProtectedRequests,
    fetchJobs,
    setClips,
    setProjects,
    setProjectsError,
    setProjectsStatus,
    setSourceMessage,
    setSourceState,
  ]);

  useEffect(() => {
    if (!canUseProtectedRequests) {
      if (!pauseReason) {
        setSourceState('loading');
        setSourceMessage(null);
        return;
      }

      setSourceState('auth_blocked');
      setSourceMessage(resolveSubtitleSourceBlockedMessage(pauseReason));
      return;
    }

    void loadSources();
  }, [canUseProtectedRequests, loadSources, pauseReason, setSourceMessage, setSourceState]);

  useEffect(() => {
    if (canUseProtectedRequests || pauseReason || sourceState !== 'loading') {
      return;
    }

    const recoveryTimer = window.setTimeout(() => {
      void loadSources({ forceAuthRecovery: true });
    }, AUTH_BOOTSTRAP_RECOVERY_MS);

    return () => window.clearTimeout(recoveryTimer);
  }, [canUseProtectedRequests, loadSources, pauseReason, sourceState]);
}

export function useLockedClipSelectionEffect({
  clips,
  lockedToClip,
  selection,
  targetClip,
}: {
  clips: Clip[];
  lockedToClip: boolean;
  selection: SubtitleSelectionState;
  targetClip: Clip | null;
}) {
  const wasLockedRef = useRef(lockedToClip);
  const { setMode, setSelectedClip, setSelectedProjectId } = selection;

  useEffect(() => {
    if (lockedToClip && targetClip) {
      setMode('clip');
      setSelectedProjectId(null);
      setSelectedClip(targetClip);
      wasLockedRef.current = true;
      return;
    }

    if (wasLockedRef.current && !lockedToClip) {
      setMode('project');
      setSelectedClip(null);
      setSelectedProjectId(null);
    }

    wasLockedRef.current = lockedToClip;
  }, [lockedToClip, setMode, setSelectedClip, setSelectedProjectId, targetClip]);

  useEffect(() => {
    if (!lockedToClip || !targetClip || clips.length === 0) {
      return;
    }

    const resolvedClip = reconcileLockedClip(clips, targetClip);
    if (
      resolvedClip !== selection.selectedClip
      && !(
        resolvedClip
        && selection.selectedClip
        && hasSameLockedClipContext(resolvedClip, selection.selectedClip)
      )
    ) {
      setSelectedClip(resolvedClip);
    }
  }, [clips, lockedToClip, selection.selectedClip, setSelectedClip, targetClip]);
}
