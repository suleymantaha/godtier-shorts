import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';

import { clipsApi } from '../../api/client';
import { useAuthRuntimeStore } from '../../auth/runtime';
import { useJobStore } from '../../store/useJobStore';
import type { Clip, Job } from '../../types';
import { isAppError } from '../../api/errors';

export type GalleryState = 'loading' | 'processing' | 'error' | 'auth_blocked' | 'empty' | 'ready';
export type ClipSortOrder = 'newest' | 'oldest';

const POLL_INTERVAL_MS = 10000;
const RETRY_ON_ERROR_MS = 3000;
const CLIPS_PAGE_SIZE = 200;
const ALL_PROJECTS_FILTER = 'all';
const AUTH_BLOCKING_CODES = new Set(['auth_provider_unavailable', 'auth_revalidation_required', 'forbidden', 'token_expired', 'unauthorized']);
const CLIP_PRODUCING_JOB_PREFIXES = ['batch_', 'manualcut_', 'manual_'];

function isSameClip(left: Clip, right: Clip) {
  return left.name === right.name && left.project === right.project;
}

export function useClipGalleryController() {
  const canUseProtectedRequests = useAuthRuntimeStore((state) => state.canUseProtectedRequests);
  const pauseReason = useAuthRuntimeStore((state) => state.pauseReason);
  const [clips, setClips] = useState<Clip[]>([]);
  const [shareClip, setShareClip] = useState<Clip | null>(null);
  const [deleteClip, setDeleteClip] = useState<Clip | null>(null);
  const [state, setState] = useState<GalleryState>('loading');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [projectFilter, setProjectFilter] = useState(ALL_PROJECTS_FILTER);
  const [sortOrder, setSortOrder] = useState<ClipSortOrder>('newest');
  const [isDeleting, setIsDeleting] = useState(false);
  const [staleRefreshWarning, setStaleRefreshWarning] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const clipReadySignal = useJobStore((store) => store.clipReadySignal);
  const refreshClipsTrigger = useJobStore((store) => store.refreshClipsTrigger);
  const jobs = useJobStore((store) => store.jobs);
  const hasLoadedOnce = useRef(false);
  const cancelledRef = useRef(false);
  const retryTimerRef = useRef<number | null>(null);
  const hasActiveClipProducingJobs = jobs.some(isActiveClipProducingJob);

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
  }, []);

  const fetchClips = useCallback(async () => {
    if (!canUseProtectedRequests) {
      return;
    }

    try {
      const data = await clipsApi.list(1, CLIPS_PAGE_SIZE);
      if (cancelledRef.current) {
        return;
      }

      hasLoadedOnce.current = data.clips.length > 0;
      setClips(data.clips);
      setTotal(data.total ?? data.clips.length);
      setHasMore(Boolean(data.has_more));
      setState(resolveGalleryState(data.clips.length, hasActiveClipProducingJobs));
      setErrorMsg(null);
      setStaleRefreshWarning(null);
      clearRetryTimer();
    } catch (error) {
      if (cancelledRef.current) {
        return;
      }

      const message = error instanceof Error ? error.message : 'Klipler yuklenemedi.';
      setErrorMsg(message);

      if (isAppError(error) && AUTH_BLOCKING_CODES.has(error.code)) {
        setState('auth_blocked');
        clearRetryTimer();
        return;
      }

      if (!hasLoadedOnce.current) {
        setState('error');
        scheduleRetry();
        return;
      }

      setStaleRefreshWarning('Library refresh failed. Showing last synced clips.');
    }
  }, [canUseProtectedRequests, clearRetryTimer, hasActiveClipProducingJobs, scheduleRetry]);

  useClipGalleryPolling(cancelledRef, canUseProtectedRequests, clearRetryTimer, fetchClips, retryTick);
  useClipGalleryRefresh(canUseProtectedRequests, fetchClips, clipReadySignal, refreshClipsTrigger);

  useEffect(() => {
    if (canUseProtectedRequests) {
      return;
    }

    setState('auth_blocked');
    setErrorMsg(resolveAuthBlockedMessage(pauseReason));
    clearRetryTimer();
  }, [canUseProtectedRequests, clearRetryTimer, pauseReason]);

  useEffect(() => {
    if (!canUseProtectedRequests || clips.length > 0) {
      return;
    }

    if (state === 'auth_blocked' || state === 'error' || state === 'loading') {
      return;
    }

    setState(hasActiveClipProducingJobs ? 'processing' : 'empty');
  }, [canUseProtectedRequests, clips.length, hasActiveClipProducingJobs, state]);

  useEffect(() => {
    if (projectFilter === ALL_PROJECTS_FILTER) {
      return;
    }

    const projectStillVisible = clips.some((clip) => (clip.project ?? '') === projectFilter);
    if (!projectStillVisible) {
      setProjectFilter(ALL_PROJECTS_FILTER);
    }
  }, [clips, projectFilter]);

  const handleRetry = useCallback(() => {
    setStaleRefreshWarning(null);
    setState('loading');
    setRetryTick((tick) => tick + 1);
  }, []);

  const handleRequestDelete = useCallback((clip: Clip) => {
    setDeleteError(null);
    setDeleteClip(clip);
  }, []);

  const handleCloseDelete = useCallback(() => {
    if (isDeleting) {
      return;
    }
    setDeleteClip(null);
    setDeleteError(null);
  }, [isDeleting]);

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteClip?.project || isDeleting) {
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await clipsApi.delete(deleteClip.project, deleteClip.name);
      setClips((current) => current.filter((clip) => !isSameClip(clip, deleteClip)));
      setTotal((current) => Math.max(0, current - 1));
      if (clips.length <= 1) {
        setState(hasActiveClipProducingJobs ? 'processing' : 'empty');
      }
      setShareClip((current) => (current && isSameClip(current, deleteClip) ? null : current));
      setDeleteClip(null);
      void fetchClips();
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : 'Klip silinemedi.');
    } finally {
      setIsDeleting(false);
    }
  }, [clips.length, deleteClip, fetchClips, hasActiveClipProducingJobs, isDeleting]);

  const projectOptions = [
    { label: 'All Projects', value: ALL_PROJECTS_FILTER },
    ...Array.from(new Set(clips.map((clip) => clip.project).filter((project): project is string => Boolean(project))))
      .sort((left, right) => left.localeCompare(right))
      .map((project) => ({ label: project, value: project })),
  ];

  const visibleClips = [...clips]
    .filter((clip) => projectFilter === ALL_PROJECTS_FILTER || clip.project === projectFilter)
    .sort((left, right) => {
      const delta = left.created_at - right.created_at;
      return sortOrder === 'oldest' ? delta : -delta;
    });

  return {
    clips: visibleClips,
    deleteClip,
    deleteError,
    errorMsg,
    handleCloseDelete,
    handleConfirmDelete,
    handleRequestDelete,
    handleRetry,
    hasMore,
    isDeleting,
    loadedCount: clips.length,
    pageSizeLimit: CLIPS_PAGE_SIZE,
    projectFilter,
    projectOptions,
    setProjectFilter,
    setShareClip,
    setSortOrder,
    shareClip,
    sortOrder,
    staleRefreshWarning,
    state,
    productionInProgress: hasActiveClipProducingJobs && clips.length > 0,
    totalCount: total,
    visibleCount: visibleClips.length,
  };
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
  if (pauseReason === 'token_expired') {
    return 'Oturum suresi doldugu icin klip kutuphanesi gecici olarak duraklatildi.';
  }

  if (pauseReason === 'forbidden') {
    return 'Bu hesapla klip kutuphanesine erisim izni bulunmuyor.';
  }

  if (pauseReason === 'auth_provider_unavailable') {
    return 'Kimlik dogrulama servisi gecici olarak erisilemiyor.';
  }

  if (pauseReason === 'network_offline' || pauseReason === 'auth_revalidation_required') {
    return 'Baglanti veya oturum yenileme sorunu nedeniyle klip kutuphanesi beklemede.';
  }

  return 'Klip kutuphanesi icin backend oturumu dogrulanamadi.';
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
