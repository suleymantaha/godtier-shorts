import { useCallback, useEffect, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from 'react';

import { authApi, clipsApi } from '../../api/client';
import { useAuthRuntimeStore } from '../../auth/runtime';
import { tSafe } from '../../i18n';
import { useJobStore } from '../../store/useJobStore';
import type { Clip, Job, OwnershipDiagnosticsResponse } from '../../types';
import { isAppError } from '../../api/errors';

export type GalleryState = 'loading' | 'processing' | 'error' | 'auth_blocked' | 'empty' | 'ready';
export type ClipSortOrder = 'newest' | 'oldest';

const POLL_INTERVAL_MS = 10000;
const RETRY_ON_ERROR_MS = 3000;
const AUTH_BOOTSTRAP_RECOVERY_MS = 2500;
const CLIPS_PAGE_SIZE = 200;
const ALL_PROJECTS_FILTER = 'all';
const AUTH_BLOCKING_CODES = new Set(['auth_provider_unavailable', 'auth_revalidation_required', 'forbidden', 'token_expired', 'unauthorized']);
const CLIP_PRODUCING_JOB_PREFIXES = ['batch_', 'manualcut_', 'manual_'];

function isSameClip(left: Clip, right: Clip) {
  return left.name === right.name && left.project === right.project;
}

function useClipGalleryState() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [shareClip, setShareClip] = useState<Clip | null>(null);
  const [deleteClip, setDeleteClip] = useState<Clip | null>(null);
  const [ownershipDiagnostics, setOwnershipDiagnostics] = useState<OwnershipDiagnosticsResponse | null>(null);
  const [ownershipNotice, setOwnershipNotice] = useState<string | null>(null);
  const [ownershipNoticeTone, setOwnershipNoticeTone] = useState<'danger' | 'info'>('info');
  const [state, setState] = useState<GalleryState>('loading');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [isClaimingProjectId, setIsClaimingProjectId] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [projectFilter, setProjectFilter] = useState(ALL_PROJECTS_FILTER);
  const [sortOrder, setSortOrder] = useState<ClipSortOrder>('newest');
  const [isDeleting, setIsDeleting] = useState(false);
  const [staleRefreshWarning, setStaleRefreshWarning] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);

  return {
    clips,
    deleteClip,
    deleteError,
    errorMsg,
    hasMore,
    isClaimingProjectId,
    isDeleting,
    ownershipDiagnostics,
    ownershipNotice,
    ownershipNoticeTone,
    projectFilter,
    retryTick,
    setClips,
    setDeleteClip,
    setDeleteError,
    setErrorMsg,
    setHasMore,
    setIsClaimingProjectId,
    setIsDeleting,
    setOwnershipDiagnostics,
    setOwnershipNotice,
    setOwnershipNoticeTone,
    setProjectFilter,
    setRetryTick,
    setShareClip,
    setSortOrder,
    setStaleRefreshWarning,
    setState,
    setTotal,
    shareClip,
    sortOrder,
    staleRefreshWarning,
    state,
    total,
  };
}

function useClipGalleryRetry(
  cancelledRef: RefObject<boolean>,
  setRetryTick: Dispatch<SetStateAction<number>>,
) {
  const retryTimerRef = useRef<number | null>(null);

  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }, []);

  const scheduleRetry = useCallback(() => {
    if (retryTimerRef.current !== null) {
      return;
    }

    retryTimerRef.current = window.setTimeout(() => {
      retryTimerRef.current = null;
      if (!cancelledRef.current) {
        setRetryTick((tick) => tick + 1);
      }
    }, RETRY_ON_ERROR_MS);
  }, [cancelledRef, setRetryTick]);

  return {
    clearRetryTimer,
    scheduleRetry,
  };
}

function buildProjectOptions(clips: Clip[]) {
  return [
    { label: tSafe('clipGallery.toolbar.allProjects'), value: ALL_PROJECTS_FILTER },
    ...Array.from(new Set(clips.map((clip) => clip.project).filter((project): project is string => Boolean(project))))
      .sort((left, right) => left.localeCompare(right))
      .map((project) => ({ label: project, value: project })),
  ];
}

function buildVisibleClips(clips: Clip[], projectFilter: string, sortOrder: ClipSortOrder) {
  return [...clips]
    .filter((clip) => projectFilter === ALL_PROJECTS_FILTER || clip.project === projectFilter)
    .sort((left, right) => {
      const delta = left.created_at - right.created_at;
      return sortOrder === 'oldest' ? delta : -delta;
    });
}

function useClipGalleryFetch({
  canUseProtectedRequests,
  clearRetryTimer,
  clipsState,
  cancelledRef,
  hasActiveClipProducingJobs,
  hasLoadedOnceRef,
  scheduleRetry,
}: {
  canUseProtectedRequests: boolean;
  clearRetryTimer: () => void;
  clipsState: ReturnType<typeof useClipGalleryState>;
  cancelledRef: RefObject<boolean>;
  hasActiveClipProducingJobs: boolean;
  hasLoadedOnceRef: RefObject<boolean>;
  scheduleRetry: () => void;
}) {
  return useCallback(async (options?: { forceAuthRecovery?: boolean }) => {
    if (!canUseProtectedRequests && !options?.forceAuthRecovery) {
      return;
    }

    try {
      const data = await clipsApi.list(1, CLIPS_PAGE_SIZE);
      if (cancelledRef.current) {
        return;
      }

      hasLoadedOnceRef.current = data.clips.length > 0;
      clipsState.setClips(data.clips);
      clipsState.setTotal(data.total ?? data.clips.length);
      clipsState.setHasMore(Boolean(data.has_more));
      clipsState.setState(resolveGalleryState(data.clips.length, hasActiveClipProducingJobs));
      clipsState.setErrorMsg(null);
      clipsState.setStaleRefreshWarning(null);
      clearRetryTimer();
    } catch (error) {
      if (cancelledRef.current) {
        return;
      }

      const message = error instanceof Error ? error.message : tSafe('clipGalleryErrors.loadFailed');
      clipsState.setErrorMsg(message);

      if (isAppError(error) && AUTH_BLOCKING_CODES.has(error.code)) {
        clipsState.setState('auth_blocked');
        clearRetryTimer();
        return;
      }

      if (!hasLoadedOnceRef.current) {
        clipsState.setState('error');
        scheduleRetry();
        return;
      }

      clipsState.setStaleRefreshWarning(tSafe('clipGalleryErrors.staleRefreshWarning'));
    }
  }, [canUseProtectedRequests, cancelledRef, clearRetryTimer, clipsState, hasActiveClipProducingJobs, hasLoadedOnceRef, scheduleRetry]);
}

function useClipGalleryStateEffects({
  canUseProtectedRequests,
  clearRetryTimer,
  clips,
  hasActiveClipProducingJobs,
  pauseReason,
  projectFilter,
  setErrorMsg,
  setProjectFilter,
  setState,
  state,
}: {
  canUseProtectedRequests: boolean;
  clearRetryTimer: () => void;
  clips: Clip[];
  hasActiveClipProducingJobs: boolean;
  pauseReason: string | null;
  projectFilter: string;
  setErrorMsg: Dispatch<SetStateAction<string | null>>;
  setProjectFilter: Dispatch<SetStateAction<string>>;
  setState: Dispatch<SetStateAction<GalleryState>>;
  state: GalleryState;
}) {
  useEffect(() => {
    if (canUseProtectedRequests) {
      return;
    }

    if (!pauseReason) {
      // Auth runtime is still bootstrapping/refreshing; keep gallery in loading mode.
      setState('loading');
      setErrorMsg(null);
      clearRetryTimer();
      return;
    }

    setState('auth_blocked');
    setErrorMsg(resolveAuthBlockedMessage(pauseReason));
    clearRetryTimer();
  }, [canUseProtectedRequests, clearRetryTimer, pauseReason, setErrorMsg, setState]);

  useEffect(() => {
    if (!canUseProtectedRequests || state !== 'auth_blocked') {
      return;
    }

    // Runtime recovered: switch back to loading so polling can refresh data.
    setErrorMsg(null);
    setState('loading');
  }, [canUseProtectedRequests, setErrorMsg, setState, state]);

  useEffect(() => {
    if (!canUseProtectedRequests || clips.length > 0) {
      return;
    }

    if (state === 'auth_blocked' || state === 'error' || state === 'loading') {
      return;
    }

    setState(hasActiveClipProducingJobs ? 'processing' : 'empty');
  }, [canUseProtectedRequests, clips.length, hasActiveClipProducingJobs, setState, state]);

  useEffect(() => {
    if (projectFilter === ALL_PROJECTS_FILTER) {
      return;
    }

    const projectStillVisible = clips.some((clip) => (clip.project ?? '') === projectFilter);
    if (!projectStillVisible) {
      setProjectFilter(ALL_PROJECTS_FILTER);
    }
  }, [clips, projectFilter, setProjectFilter]);
}

function useClipGalleryDeleteActions({
  clipsLength,
  deleteClip,
  fetchClips,
  hasActiveClipProducingJobs,
  isDeleting,
  setClips,
  setDeleteClip,
  setDeleteError,
  setIsDeleting,
  setRetryTick,
  setShareClip,
  setState,
  setStaleRefreshWarning,
  setTotal,
}: {
  clipsLength: number;
  deleteClip: Clip | null;
  fetchClips: (options?: { forceAuthRecovery?: boolean }) => Promise<void>;
  hasActiveClipProducingJobs: boolean;
  isDeleting: boolean;
  setClips: Dispatch<SetStateAction<Clip[]>>;
  setDeleteClip: Dispatch<SetStateAction<Clip | null>>;
  setDeleteError: Dispatch<SetStateAction<string | null>>;
  setIsDeleting: Dispatch<SetStateAction<boolean>>;
  setRetryTick: Dispatch<SetStateAction<number>>;
  setShareClip: Dispatch<SetStateAction<Clip | null>>;
  setState: Dispatch<SetStateAction<GalleryState>>;
  setStaleRefreshWarning: Dispatch<SetStateAction<string | null>>;
  setTotal: Dispatch<SetStateAction<number>>;
}) {
  const handleRetry = useClipGalleryRetryAction(fetchClips, setDeleteError, setRetryTick, setStaleRefreshWarning, setState);
  const handleRequestDelete = useCallback((clip: Clip) => { setDeleteError(null); setDeleteClip(clip); }, [setDeleteClip, setDeleteError]);

  const handleCloseDelete = useCallback(() => {
    if (isDeleting) {
      return;
    }
    setDeleteClip(null);
    setDeleteError(null);
  }, [isDeleting, setDeleteClip, setDeleteError]);

  const finalizeDeletedClip = useCallback(() => {
    setClips((current) => current.filter((clip) => !isSameClip(clip, deleteClip as Clip)));
    setTotal((current) => Math.max(0, current - 1));
    if (clipsLength <= 1) {
      setState(hasActiveClipProducingJobs ? 'processing' : 'empty');
    }
    setShareClip((current) => (current && isSameClip(current, deleteClip as Clip) ? null : current));
    setDeleteClip(null);
  }, [clipsLength, deleteClip, hasActiveClipProducingJobs, setClips, setDeleteClip, setShareClip, setState, setTotal]);

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteClip?.project || isDeleting) {
      return;
    }
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await clipsApi.delete(deleteClip.project, deleteClip.name);
      finalizeDeletedClip();
      void fetchClips();
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : tSafe('clipGalleryErrors.deleteFailed'));
    } finally {
      setIsDeleting(false);
    }
  }, [
    deleteClip,
    finalizeDeletedClip,
    fetchClips,
    isDeleting,
    setDeleteError,
    setIsDeleting,
  ]);

  return {
    handleCloseDelete,
    handleConfirmDelete,
    handleRequestDelete,
    handleRetry,
  };
}

function useClipGalleryRetryAction(
  fetchClips: (options?: { forceAuthRecovery?: boolean }) => Promise<void>,
  setDeleteError: Dispatch<SetStateAction<string | null>>,
  setRetryTick: Dispatch<SetStateAction<number>>,
  setStaleRefreshWarning: Dispatch<SetStateAction<string | null>>,
  setState: Dispatch<SetStateAction<GalleryState>>,
) {
  return useCallback(() => {
    setDeleteError(null);
    setRetryTick((tick) => tick + 1);
    setStaleRefreshWarning(null);
    setState('loading');
    void fetchClips({ forceAuthRecovery: true });
  }, [fetchClips, setDeleteError, setRetryTick, setStaleRefreshWarning, setState]);
}

function useOwnershipRecovery({
  canUseProtectedRequests,
  cancelledRef,
  clipsState,
  fetchClips,
}: {
  canUseProtectedRequests: boolean;
  cancelledRef: RefObject<boolean>;
  clipsState: ReturnType<typeof useClipGalleryState>;
  fetchClips: (options?: { forceAuthRecovery?: boolean }) => Promise<void>;
}) {
  const {
    isClaimingProjectId,
    setIsClaimingProjectId,
    setOwnershipDiagnostics,
    setOwnershipNotice,
    setOwnershipNoticeTone,
  } = clipsState;

  const fetchOwnershipDiagnostics = useCallback(async () => {
    if (!canUseProtectedRequests) {
      return;
    }

    try {
      const diagnostics = await authApi.ownershipDiagnostics();
      if (cancelledRef.current) {
        return;
      }
      setOwnershipDiagnostics(diagnostics);
    } catch (error) {
      if (cancelledRef.current) {
        return;
      }
      if (isAppError(error) && (error.code === 'forbidden' || AUTH_BLOCKING_CODES.has(error.code))) {
        return;
      }
      setOwnershipNotice(error instanceof Error ? error.message : tSafe('clipGalleryErrors.ownershipUnavailable'));
      setOwnershipNoticeTone('danger');
    }
  }, [canUseProtectedRequests, cancelledRef, setOwnershipDiagnostics, setOwnershipNotice, setOwnershipNoticeTone]);

  useEffect(() => {
    if (!canUseProtectedRequests) {
      setOwnershipNotice(null);
      setIsClaimingProjectId(null);
      return;
    }

    void fetchOwnershipDiagnostics();
  }, [canUseProtectedRequests, fetchOwnershipDiagnostics, setIsClaimingProjectId, setOwnershipNotice]);

  const handleClaimProject = useCallback(async (projectId: string) => {
    if (!canUseProtectedRequests || isClaimingProjectId) {
      return;
    }

    setOwnershipNotice(null);
    setIsClaimingProjectId(projectId);
    try {
      const response = await authApi.claimProjectOwnership(projectId);
      if (cancelledRef.current) {
        return;
      }
      setOwnershipNotice(tSafe('clipGalleryErrors.projectClaimed', { projectId: response.new_project_id }));
      setOwnershipNoticeTone('info');
      await Promise.all([
        fetchClips(),
        fetchOwnershipDiagnostics(),
      ]);
    } catch (error) {
      if (cancelledRef.current) {
        return;
      }
      setOwnershipNotice(error instanceof Error ? error.message : tSafe('clipGalleryErrors.projectClaimFailed'));
      setOwnershipNoticeTone('danger');
    } finally {
      if (!cancelledRef.current) {
        setIsClaimingProjectId(null);
      }
    }
  }, [
    canUseProtectedRequests,
    cancelledRef,
    fetchClips,
    fetchOwnershipDiagnostics,
    isClaimingProjectId,
    setIsClaimingProjectId,
    setOwnershipNotice,
    setOwnershipNoticeTone,
  ]);

  return {
    handleClaimProject,
  };
}

function buildClipGalleryViewModel({
  backendIdentity,
  clipsState,
  deleteActions,
  hasActiveClipProducingJobs,
  ownershipRecovery,
  projectOptions,
  visibleClips,
}: {
  backendIdentity: ReturnType<typeof useAuthRuntimeStore.getState>['backendIdentity'];
  clipsState: ReturnType<typeof useClipGalleryState>;
  deleteActions: ReturnType<typeof useClipGalleryDeleteActions>;
  hasActiveClipProducingJobs: boolean;
  ownershipRecovery: ReturnType<typeof useOwnershipRecovery>;
  projectOptions: Array<{ label: string; value: string }>;
  visibleClips: Clip[];
}) {
  return {
    authMode: clipsState.ownershipDiagnostics?.auth_mode ?? backendIdentity?.authMode ?? null,
    clips: visibleClips,
    currentSubjectHash: clipsState.ownershipDiagnostics?.current_subject_hash ?? backendIdentity?.subjectHash ?? null,
    deleteClip: clipsState.deleteClip,
    deleteError: clipsState.deleteError,
    errorMsg: clipsState.errorMsg,
    handleClaimProject: ownershipRecovery.handleClaimProject,
    hasMore: clipsState.hasMore,
    isClaimingProjectId: clipsState.isClaimingProjectId,
    isDeleting: clipsState.isDeleting,
    loadedCount: clipsState.clips.length,
    ownershipNotice: clipsState.ownershipNotice,
    ownershipNoticeTone: clipsState.ownershipNoticeTone,
    pageSizeLimit: CLIPS_PAGE_SIZE,
    productionInProgress: hasActiveClipProducingJobs && clipsState.clips.length > 0,
    projectFilter: clipsState.projectFilter,
    projectOptions,
    reclaimableProjects: clipsState.ownershipDiagnostics?.reclaimable_projects ?? [],
    setProjectFilter: clipsState.setProjectFilter,
    setShareClip: clipsState.setShareClip,
    setSortOrder: clipsState.setSortOrder,
    shareClip: clipsState.shareClip,
    sortOrder: clipsState.sortOrder,
    staleRefreshWarning: clipsState.staleRefreshWarning,
    state: clipsState.state,
    totalCount: clipsState.total,
    visibleCount: visibleClips.length,
    ...deleteActions,
  };
}

export function useClipGalleryController() {
  const backendIdentity = useAuthRuntimeStore((state) => state.backendIdentity);
  const canUseProtectedRequests = useAuthRuntimeStore((state) => state.canUseProtectedRequests);
  const pauseReason = useAuthRuntimeStore((state) => state.pauseReason);
  const clipsState = useClipGalleryState();
  const clipReadySignal = useJobStore((store) => store.clipReadySignal);
  const refreshClipsTrigger = useJobStore((store) => store.refreshClipsTrigger);
  const jobs = useJobStore((store) => store.jobs);
  const hasLoadedOnceRef = useRef(false);
  const cancelledRef = useRef(false);
  const hasActiveClipProducingJobs = jobs.some(isActiveClipProducingJob);
  const { clearRetryTimer, scheduleRetry } = useClipGalleryRetry(cancelledRef, clipsState.setRetryTick);
  const fetchClips = useClipGalleryFetch({
    canUseProtectedRequests,
    cancelledRef,
    clearRetryTimer,
    clipsState,
    hasActiveClipProducingJobs,
    hasLoadedOnceRef,
    scheduleRetry,
  });
  const ownershipRecovery = useOwnershipRecovery({
    canUseProtectedRequests,
    cancelledRef,
    clipsState,
    fetchClips,
  });

  useClipGalleryPolling(cancelledRef, canUseProtectedRequests, clearRetryTimer, fetchClips, clipsState.retryTick);
  useClipGalleryRefresh(canUseProtectedRequests, fetchClips, clipReadySignal, refreshClipsTrigger);
  useClipGalleryBootstrapRecovery(
    canUseProtectedRequests,
    fetchClips,
    pauseReason,
    clipsState.state,
  );
  useClipGalleryStateEffects({
    canUseProtectedRequests,
    clearRetryTimer,
    clips: clipsState.clips,
    hasActiveClipProducingJobs,
    pauseReason,
    projectFilter: clipsState.projectFilter,
    setErrorMsg: clipsState.setErrorMsg,
    setProjectFilter: clipsState.setProjectFilter,
    setState: clipsState.setState,
    state: clipsState.state,
  });
  const deleteActions = useClipGalleryDeleteActions({
    clipsLength: clipsState.clips.length,
    deleteClip: clipsState.deleteClip,
    fetchClips,
    hasActiveClipProducingJobs,
    isDeleting: clipsState.isDeleting,
    setClips: clipsState.setClips,
    setDeleteClip: clipsState.setDeleteClip,
    setDeleteError: clipsState.setDeleteError,
    setIsDeleting: clipsState.setIsDeleting,
    setRetryTick: clipsState.setRetryTick,
    setShareClip: clipsState.setShareClip,
    setState: clipsState.setState,
    setStaleRefreshWarning: clipsState.setStaleRefreshWarning,
    setTotal: clipsState.setTotal,
  });
  const projectOptions = buildProjectOptions(clipsState.clips);
  const visibleClips = buildVisibleClips(clipsState.clips, clipsState.projectFilter, clipsState.sortOrder);

  return buildClipGalleryViewModel({
    backendIdentity,
    clipsState,
    deleteActions,
    hasActiveClipProducingJobs,
    ownershipRecovery,
    projectOptions,
    visibleClips,
  });
}

function isActiveClipProducingJob(job: Job): boolean {
  if (job.status !== 'queued' && job.status !== 'processing') {
    return false;
  }

  return CLIP_PRODUCING_JOB_PREFIXES.some((prefix) => job.job_id.startsWith(prefix));
}

function resolveGalleryState(clipCount: number, hasActiveClipProducingJobs: boolean): GalleryState {
  if (clipCount > 0) {
    return 'ready';
  }

  return hasActiveClipProducingJobs ? 'processing' : 'empty';
}

function resolveAuthBlockedMessage(pauseReason: string | null): string {
  if (pauseReason === 'unauthorized') {
    return tSafe('clipGalleryErrors.authBlocked.unauthorized');
  }

  if (pauseReason === 'token_expired') {
    return tSafe('clipGalleryErrors.authBlocked.tokenExpired');
  }

  if (pauseReason === 'forbidden') {
    return tSafe('clipGalleryErrors.authBlocked.forbidden');
  }

  if (pauseReason === 'auth_provider_unavailable') {
    return tSafe('clipGalleryErrors.authBlocked.providerUnavailable');
  }

  if (pauseReason === 'network_offline' || pauseReason === 'auth_revalidation_required') {
    return tSafe('clipGalleryErrors.authBlocked.networkOffline');
  }

  return tSafe('clipGalleryErrors.authBlocked.fallback');
}

function useClipGalleryPolling(
  cancelledRef: RefObject<boolean>,
  canUseProtectedRequests: boolean,
  clearRetryTimer: () => void,
  fetchClips: () => Promise<void>,
  retryTick: number,
) {
  useEffect(() => {
    cancelledRef.current = false;

    if (!canUseProtectedRequests) {
      return () => {
        cancelledRef.current = true;
        clearRetryTimer();
      };
    }

    const initialFetchTimer = window.setTimeout(() => {
      void fetchClips();
    }, 0);
    const interval = window.setInterval(() => void fetchClips(), POLL_INTERVAL_MS);

    return () => {
      cancelledRef.current = true;
      clearTimeout(initialFetchTimer);
      clearInterval(interval);
      clearRetryTimer();
    };
  }, [cancelledRef, canUseProtectedRequests, clearRetryTimer, fetchClips, retryTick]);
}

function useClipGalleryRefresh(
  canUseProtectedRequests: boolean,
  fetchClips: () => Promise<void>,
  clipReadySignal: number,
  refreshClipsTrigger: number,
) {
  useEffect(() => {
    if (!canUseProtectedRequests || (clipReadySignal <= 0 && refreshClipsTrigger <= 0)) {
      return;
    }

    const refreshTimer = window.setTimeout(() => {
      void fetchClips();
    }, 0);

    return () => clearTimeout(refreshTimer);
  }, [canUseProtectedRequests, clipReadySignal, fetchClips, refreshClipsTrigger]);
}

function useClipGalleryBootstrapRecovery(
  canUseProtectedRequests: boolean,
  fetchClips: (options?: { forceAuthRecovery?: boolean }) => Promise<void>,
  pauseReason: string | null,
  state: GalleryState,
) {
  useEffect(() => {
    if (canUseProtectedRequests || pauseReason || state !== 'loading') {
      return;
    }

    const recoveryTimer = window.setTimeout(() => {
      void fetchClips({ forceAuthRecovery: true });
    }, AUTH_BOOTSTRAP_RECOVERY_MS);

    return () => window.clearTimeout(recoveryTimer);
  }, [canUseProtectedRequests, fetchClips, pauseReason, state]);
}
