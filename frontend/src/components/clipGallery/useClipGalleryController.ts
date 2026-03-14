import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';

import { clipsApi } from '../../api/client';
import { useJobStore } from '../../store/useJobStore';
import type { Clip } from '../../types';

export type GalleryState = 'loading' | 'error' | 'empty' | 'ready';
export type ClipSortOrder = 'newest' | 'oldest';

const POLL_INTERVAL_MS = 30000;
const RETRY_ON_ERROR_MS = 3000;
const CLIPS_PAGE_SIZE = 200;
const ALL_PROJECTS_FILTER = 'all';

function isSameClip(left: Clip, right: Clip) {
  return left.name === right.name && left.project === right.project;
}

export function useClipGalleryController() {
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
  const [retryTick, setRetryTick] = useState(0);
  const refreshClipsTrigger = useJobStore((store) => store.refreshClipsTrigger);
  const hasLoadedOnce = useRef(false);
  const cancelledRef = useRef(false);
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
  }, []);

  const fetchClips = useCallback(async () => {
    try {
      const data = await clipsApi.list(1, CLIPS_PAGE_SIZE);
      if (cancelledRef.current) {
        return;
      }

      hasLoadedOnce.current = data.clips.length > 0;
      setClips(data.clips);
      setTotal(data.total ?? data.clips.length);
      setHasMore(Boolean(data.has_more));
      setState(data.clips.length > 0 ? 'ready' : 'empty');
      setErrorMsg(null);
      clearRetryTimer();
    } catch (error) {
      if (cancelledRef.current) {
        return;
      }

      const message = error instanceof Error ? error.message : 'Klipler yuklenemedi.';
      setErrorMsg(message);

      if (!hasLoadedOnce.current) {
        setState('error');
        scheduleRetry();
      }
    }
  }, [clearRetryTimer, scheduleRetry]);

  useClipGalleryPolling(cancelledRef, clearRetryTimer, fetchClips, retryTick);
  useClipGalleryRefresh(fetchClips, refreshClipsTrigger);

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
        setState('empty');
      }
      setShareClip((current) => (current && isSameClip(current, deleteClip) ? null : current));
      setDeleteClip(null);
      void fetchClips();
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : 'Klip silinemedi.');
    } finally {
      setIsDeleting(false);
    }
  }, [clips.length, deleteClip, fetchClips, isDeleting]);

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
    state,
    totalCount: total,
    visibleCount: visibleClips.length,
  };
}

function useClipGalleryPolling(
  cancelledRef: RefObject<boolean>,
  clearRetryTimer: () => void,
  fetchClips: () => Promise<void>,
  retryTick: number,
) {
  useEffect(() => {
    cancelledRef.current = false;
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
  }, [cancelledRef, clearRetryTimer, fetchClips, retryTick]);
}

function useClipGalleryRefresh(
  fetchClips: () => Promise<void>,
  refreshClipsTrigger: number,
) {
  useEffect(() => {
    if (refreshClipsTrigger <= 0) {
      return;
    }

    const refreshTimer = window.setTimeout(() => {
      void fetchClips();
    }, 0);

    return () => clearTimeout(refreshTimer);
  }, [fetchClips, refreshClipsTrigger]);
}
