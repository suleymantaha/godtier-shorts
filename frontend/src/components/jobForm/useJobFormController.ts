import { useEffect, useId, useRef, useState, type Dispatch, type FormEvent, type SetStateAction } from 'react';

import { jobsApi } from '../../api/client';
import { useDebouncedEffect } from '../../hooks/useDebouncedEffect';
import type { RequestedSubtitleLayout, StyleName, SubtitleAnimationType } from '../../config/subtitleStyles';
import { useJobStore } from '../../store/useJobStore';
import type { CacheStatusResponse } from '../../types';
import {
  JOB_FORM_PREFS_STORAGE_KEY,
  buildStartJobPayload,
  readInitialAnimationType,
  readInitialEngine,
  readInitialLayout,
  readInitialStyle,
} from './helpers';

export interface JobFormProps {
  onAnimationChange?: (animationType: SubtitleAnimationType) => void;
  onSkipSubtitlesChange?: (skip: boolean) => void;
  onStyleChange?: (style: string) => void;
}

const DEFAULT_CACHE_STATUS: CacheStatusResponse = {
  project_id: null,
  project_cached: false,
  analysis_cached: false,
  render_cached: false,
  cache_scope: 'none',
  clip_count: 0,
  message: '',
};

function isLikelyYouTubeUrl(value: string): boolean {
  const lowered = value.trim().toLowerCase();
  return (lowered.startsWith('http://') || lowered.startsWith('https://'))
    && (lowered.includes('youtube.com/watch?v=') || lowered.includes('youtu.be/'));
}

function useJobFormIds() {
  return {
    animationId: useId(),
    durationMaxId: useId(),
    durationMinId: useId(),
    engineId: useId(),
    layoutId: useId(),
    numClipsId: useId(),
    resolutionId: useId(),
    styleId: useId(),
    urlId: useId(),
  };
}

function useJobFormState() {
  const [url, setUrl] = useState('');
  const [style, setStyle] = useState<StyleName>(() => readInitialStyle());
  const [animationType, setAnimationType] = useState<SubtitleAnimationType>(() => readInitialAnimationType());
  const [engine, setEngine] = useState<string>(() => readInitialEngine());
  const [layout, setLayout] = useState<RequestedSubtitleLayout>(() => readInitialLayout());
  const [skipSubtitles, setSkipSubtitles] = useState(false);
  const [numClips, setNumClips] = useState(8);
  const [autoMode, setAutoMode] = useState(true);
  const [durationMin, setDurationMin] = useState(120);
  const [durationMax, setDurationMax] = useState(180);
  const [resolution, setResolution] = useState('best');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCheckingCache, setIsCheckingCache] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [cacheStatus, setCacheStatus] = useState<CacheStatusResponse>(DEFAULT_CACHE_STATUS);
  const [forceReanalyze, setForceReanalyze] = useState(false);
  const [forceRerender, setForceRerender] = useState(false);
  const cacheRequestRef = useRef(0);

  return {
    animationType,
    autoMode,
    cacheRequestRef,
    cacheStatus,
    durationMax,
    durationMin,
    engine,
    error,
    forceReanalyze,
    forceRerender,
    infoMessage,
    isCheckingCache,
    isSubmitting,
    layout,
    numClips,
    resolution,
    setAnimationType,
    setAutoMode,
    setCacheStatus,
    setDurationMax,
    setDurationMin,
    setEngine,
    setError,
    setForceReanalyze,
    setForceRerender,
    setInfoMessage,
    setIsCheckingCache,
    setIsSubmitting,
    setLayout,
    setNumClips,
    setResolution,
    setSkipSubtitles,
    setStyle,
    setUrl,
    skipSubtitles,
    style,
    url,
  };
}

function useJobFormSyncEffects({
  animationType,
  engine,
  layout,
  onAnimationChange,
  onSkipSubtitlesChange,
  onStyleChange,
  skipSubtitles,
  style,
}: {
  animationType: SubtitleAnimationType;
  engine: string;
  layout: RequestedSubtitleLayout;
  onAnimationChange?: (animationType: SubtitleAnimationType) => void;
  onSkipSubtitlesChange?: (skip: boolean) => void;
  onStyleChange?: (style: string) => void;
  skipSubtitles: boolean;
  style: StyleName;
}) {
  useEffect(() => onStyleChange?.(style), [onStyleChange, style]);
  useEffect(() => onAnimationChange?.(animationType), [animationType, onAnimationChange]);
  useEffect(() => onSkipSubtitlesChange?.(skipSubtitles), [onSkipSubtitlesChange, skipSubtitles]);
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(JOB_FORM_PREFS_STORAGE_KEY, JSON.stringify({ animationType, engine, layout, style }));
    }
  }, [animationType, engine, layout, style]);
}

function useForceRerenderSync(forceReanalyze: boolean, setForceRerender: (value: boolean) => void) {
  useEffect(() => {
    if (forceReanalyze) {
      setForceRerender(true);
    }
  }, [forceReanalyze, setForceRerender]);
}

function resetCacheStatusState(
  setCacheStatus: (value: CacheStatusResponse) => void,
  setForceReanalyze: (value: boolean) => void,
  setForceRerender: (value: boolean) => void,
  setIsCheckingCache: (value: boolean) => void,
) {
  setCacheStatus(DEFAULT_CACHE_STATUS);
  setIsCheckingCache(false);
  setForceReanalyze(false);
  setForceRerender(false);
}

function buildCacheStatusPayload(params: {
  animationType: SubtitleAnimationType;
  autoMode: boolean;
  durationMax: number;
  durationMin: number;
  engine: string;
  layout: RequestedSubtitleLayout;
  numClips: number;
  resolution: string;
  skipSubtitles: boolean;
  style: StyleName;
  url: string;
}) {
  return buildStartJobPayload({
    ...params,
    forceReanalyze: false,
    forceRerender: false,
  });
}

function useJobFormCacheStatus({
  animationType,
  autoMode,
  cacheRequestRef,
  durationMax,
  durationMin,
  engine,
  layout,
  numClips,
  resolution,
  setCacheStatus,
  setForceReanalyze,
  setForceRerender,
  setIsCheckingCache,
  skipSubtitles,
  style,
  url,
}: {
  animationType: SubtitleAnimationType;
  autoMode: boolean;
  cacheRequestRef: React.MutableRefObject<number>;
  durationMax: number;
  durationMin: number;
  engine: string;
  layout: RequestedSubtitleLayout;
  numClips: number;
  resolution: string;
  setCacheStatus: (value: CacheStatusResponse) => void;
  setForceReanalyze: (value: boolean) => void;
  setForceRerender: (value: boolean) => void;
  setIsCheckingCache: (value: boolean) => void;
  skipSubtitles: boolean;
  style: StyleName;
  url: string;
}) {
  useDebouncedEffect(() => {
    if (!isLikelyYouTubeUrl(url)) {
      resetCacheStatusState(setCacheStatus, setForceReanalyze, setForceRerender, setIsCheckingCache);
      return;
    }

    const requestId = cacheRequestRef.current + 1;
    cacheRequestRef.current = requestId;
    setIsCheckingCache(true);
    jobsApi.cacheStatus(buildCacheStatusPayload({
      animationType,
      autoMode,
      durationMax,
      durationMin,
      engine,
      layout,
      numClips,
      resolution,
      skipSubtitles,
      style,
      url,
    }))
      .then((response) => {
        if (cacheRequestRef.current !== requestId) {
          return;
        }
        setCacheStatus(response);
        if (!response.project_cached) {
          setForceReanalyze(false);
          setForceRerender(false);
        }
      })
      .catch(() => {
        if (cacheRequestRef.current !== requestId) {
          return;
        }
        setCacheStatus(DEFAULT_CACHE_STATUS);
      })
      .finally(() => {
        if (cacheRequestRef.current === requestId) {
          setIsCheckingCache(false);
        }
      });
  }, [animationType, autoMode, durationMax, durationMin, engine, layout, numClips, resolution, skipSubtitles, style, url], 250);
}

function buildStartRequestPayload(params: {
  animationType: SubtitleAnimationType;
  autoMode: boolean;
  durationMax: number;
  durationMin: number;
  engine: string;
  forceReanalyze: boolean;
  forceRerender: boolean;
  layout: RequestedSubtitleLayout;
  numClips: number;
  resolution: string;
  skipSubtitles: boolean;
  style: StyleName;
  url: string;
}) {
  return buildStartJobPayload(params);
}

interface JobFormStartActionParams {
  animationType: SubtitleAnimationType;
  autoMode: boolean;
  durationMax: number;
  durationMin: number;
  engine: string;
  fetchJobs: () => Promise<void>;
  forceReanalyze: boolean;
  forceRerender: boolean;
  mergeJobTimelineEvent: (event: {
    at: string;
    event_id: string;
    job_id: string;
    message: string;
    progress: number;
    source?: 'api' | 'worker' | 'websocket' | 'clip_ready';
    status?: 'queued' | 'processing' | 'completed' | 'cancelled' | 'error' | 'empty';
  }) => void;
  layout: RequestedSubtitleLayout;
  numClips: number;
  isSubmitting: boolean;
  registerQueuedJob: (job: { job_id: string; message?: string; style: string; url: string }) => void;
  requestClipsRefresh: () => void;
  resolution: string;
  setError: (value: string | null) => void;
  setInfoMessage: (value: string | null) => void;
  setIsSubmitting: (value: boolean) => void;
  setUrl: (value: string) => void;
  skipSubtitles: boolean;
  style: StyleName;
  url: string;
}

async function handleStartResponse({
  fetchJobs,
  mergeJobTimelineEvent,
  registerQueuedJob,
  requestClipsRefresh,
  response,
  setInfoMessage,
  style,
  url,
}: {
  fetchJobs: () => Promise<void>;
  mergeJobTimelineEvent: (event: {
    at: string;
    event_id: string;
    job_id: string;
    message: string;
    progress: number;
    source?: 'api' | 'worker' | 'websocket' | 'clip_ready';
    status?: 'queued' | 'processing' | 'completed' | 'cancelled' | 'error' | 'empty';
  }) => void;
  registerQueuedJob: (job: { job_id: string; message?: string; style: string; url: string }) => void;
  requestClipsRefresh: () => void;
  response: Awaited<ReturnType<typeof jobsApi.start>>;
  setInfoMessage: (value: string | null) => void;
  style: StyleName;
  url: string;
}) {
  if (response.status === 'cached') {
    requestClipsRefresh();
    setInfoMessage(response.message);
    return;
  }

  if (response.job_id) {
    if (response.existing_job) {
      setInfoMessage(response.message);
    } else {
      registerQueuedJob({
        job_id: response.job_id,
        message: response.message,
        style,
        url,
      });
    }
    if (!response.existing_job && response.processing_locked === false) {
      mergeJobTimelineEvent({
        at: new Date().toISOString(),
        event_id: `${response.job_id}:optimistic-processing`,
        job_id: response.job_id,
        message: 'İşlem başlatıldı. Hazırlık aşamaları yürütülüyor...',
        progress: 1,
        source: 'api',
        status: 'processing',
      });
    }
    await fetchJobs();
  }
}

function useJobFormStartAction({
  animationType,
  autoMode,
  durationMax,
  durationMin,
  engine,
  fetchJobs,
  forceReanalyze,
  forceRerender,
  mergeJobTimelineEvent,
  layout,
  numClips,
  isSubmitting,
  registerQueuedJob,
  requestClipsRefresh,
  resolution,
  setError,
  setInfoMessage,
  setIsSubmitting,
  setUrl,
  skipSubtitles,
  style,
  url,
}: JobFormStartActionParams) {
  return async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!url || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setInfoMessage(null);
    try {
      const response = await jobsApi.start(buildStartRequestPayload({
        animationType,
        autoMode,
        durationMax,
        durationMin,
        engine,
        forceReanalyze,
        forceRerender,
        layout,
        numClips,
        resolution,
        skipSubtitles,
        style,
        url,
      }));
      await handleStartResponse({
        fetchJobs,
        mergeJobTimelineEvent,
        registerQueuedJob,
        requestClipsRefresh,
        response,
        setInfoMessage,
        style,
        url,
      });
      setUrl('');
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Job baslatilamadi.');
    } finally {
      setIsSubmitting(false);
    }
  };
}

function buildJobFormControllerModel(
  ids: ReturnType<typeof useJobFormIds>,
  state: {
    animationType: SubtitleAnimationType;
    autoMode: boolean;
    cacheStatus: CacheStatusResponse;
    durationMax: number;
    durationMin: number;
    engine: string;
    error: string | null;
    forceReanalyze: boolean;
    forceRerender: boolean;
    handleStart: (event: FormEvent<HTMLFormElement>) => Promise<void>;
    infoMessage: string | null;
    isCheckingCache: boolean;
    isSubmitting: boolean;
    layout: RequestedSubtitleLayout;
    numClips: number;
    resolution: string;
    skipSubtitles: boolean;
    style: StyleName;
    url: string;
  },
  setters: {
    setAnimationType: Dispatch<SetStateAction<SubtitleAnimationType>>;
    setAutoMode: Dispatch<SetStateAction<boolean>>;
    setDurationMax: Dispatch<SetStateAction<number>>;
    setDurationMin: Dispatch<SetStateAction<number>>;
    setEngine: Dispatch<SetStateAction<string>>;
    setForceReanalyze: Dispatch<SetStateAction<boolean>>;
    setForceRerender: Dispatch<SetStateAction<boolean>>;
    setLayout: Dispatch<SetStateAction<RequestedSubtitleLayout>>;
    setNumClips: Dispatch<SetStateAction<number>>;
    setResolution: Dispatch<SetStateAction<string>>;
    setSkipSubtitles: Dispatch<SetStateAction<boolean>>;
    setStyle: Dispatch<SetStateAction<StyleName>>;
    setUrl: Dispatch<SetStateAction<string>>;
  },
) {
  return {
    ...ids,
    ...state,
    ...setters,
  };
}

function buildJobFormViewState(
  state: ReturnType<typeof useJobFormState>,
  handleStart: (event: FormEvent<HTMLFormElement>) => Promise<void>,
) {
  return {
    animationType: state.animationType,
    autoMode: state.autoMode,
    cacheStatus: state.cacheStatus,
    durationMax: state.durationMax,
    durationMin: state.durationMin,
    engine: state.engine,
    error: state.error,
    forceReanalyze: state.forceReanalyze,
    forceRerender: state.forceRerender,
    handleStart,
    infoMessage: state.infoMessage,
    isCheckingCache: state.isCheckingCache,
    isSubmitting: state.isSubmitting,
    layout: state.layout,
    numClips: state.numClips,
    resolution: state.resolution,
    skipSubtitles: state.skipSubtitles,
    style: state.style,
    url: state.url,
  };
}

function buildJobFormSetterState(state: ReturnType<typeof useJobFormState>) {
  return {
    setAnimationType: state.setAnimationType,
    setAutoMode: state.setAutoMode,
    setDurationMax: state.setDurationMax,
    setDurationMin: state.setDurationMin,
    setEngine: state.setEngine,
    setForceReanalyze: state.setForceReanalyze,
    setForceRerender: state.setForceRerender,
    setLayout: state.setLayout,
    setNumClips: state.setNumClips,
    setResolution: state.setResolution,
    setSkipSubtitles: state.setSkipSubtitles,
    setStyle: state.setStyle,
    setUrl: state.setUrl,
  };
}

export function useJobFormController({ onAnimationChange, onSkipSubtitlesChange, onStyleChange }: JobFormProps) {
  const state = useJobFormState();
  const { fetchJobs, mergeJobTimelineEvent, registerQueuedJob, requestClipsRefresh } = useJobStore();
  const ids = useJobFormIds();

  useJobFormSyncEffects({
    animationType: state.animationType,
    engine: state.engine,
    layout: state.layout,
    onAnimationChange,
    onSkipSubtitlesChange,
    onStyleChange,
    skipSubtitles: state.skipSubtitles,
    style: state.style,
  });
  useForceRerenderSync(state.forceReanalyze, state.setForceRerender);
  useJobFormCacheStatus({
    animationType: state.animationType,
    autoMode: state.autoMode,
    cacheRequestRef: state.cacheRequestRef,
    durationMax: state.durationMax,
    durationMin: state.durationMin,
    engine: state.engine,
    layout: state.layout,
    numClips: state.numClips,
    resolution: state.resolution,
    setCacheStatus: state.setCacheStatus,
    setForceReanalyze: state.setForceReanalyze,
    setForceRerender: state.setForceRerender,
    setIsCheckingCache: state.setIsCheckingCache,
    skipSubtitles: state.skipSubtitles,
    style: state.style,
    url: state.url,
  });

  const handleStart = useJobFormStartAction({
    animationType: state.animationType,
    autoMode: state.autoMode,
    durationMax: state.durationMax,
    durationMin: state.durationMin,
    engine: state.engine,
    fetchJobs,
    forceReanalyze: state.forceReanalyze,
    forceRerender: state.forceRerender,
    isSubmitting: state.isSubmitting,
    layout: state.layout,
    mergeJobTimelineEvent,
    numClips: state.numClips,
    registerQueuedJob,
    requestClipsRefresh,
    resolution: state.resolution,
    setError: state.setError,
    setInfoMessage: state.setInfoMessage,
    setIsSubmitting: state.setIsSubmitting,
    setUrl: state.setUrl,
    skipSubtitles: state.skipSubtitles,
    style: state.style,
    url: state.url,
  });

  return buildJobFormControllerModel(ids, buildJobFormViewState(state, handleStart), buildJobFormSetterState(state));
}
