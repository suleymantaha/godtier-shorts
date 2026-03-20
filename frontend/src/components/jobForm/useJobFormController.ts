import { useEffect, useId, useRef, useState, type FormEvent } from 'react';

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

export function useJobFormController({ onAnimationChange, onSkipSubtitlesChange, onStyleChange }: JobFormProps) {
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
  const { fetchJobs, registerQueuedJob, requestClipsRefresh } = useJobStore();

  const urlId = useId();
  const styleId = useId();
  const animationId = useId();
  const engineId = useId();
  const numClipsId = useId();
  const layoutId = useId();
  const durationMinId = useId();
  const durationMaxId = useId();
  const resolutionId = useId();

  useEffect(() => onStyleChange?.(style), [onStyleChange, style]);
  useEffect(() => onAnimationChange?.(animationType), [animationType, onAnimationChange]);
  useEffect(() => onSkipSubtitlesChange?.(skipSubtitles), [onSkipSubtitlesChange, skipSubtitles]);
  useEffect(() => {
    if (forceReanalyze) {
      setForceRerender(true);
    }
  }, [forceReanalyze]);
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(JOB_FORM_PREFS_STORAGE_KEY, JSON.stringify({ animationType, engine, layout, style }));
    }
  }, [animationType, engine, layout, style]);

  useDebouncedEffect(() => {
    if (!isLikelyYouTubeUrl(url)) {
      setCacheStatus(DEFAULT_CACHE_STATUS);
      setIsCheckingCache(false);
      setForceReanalyze(false);
      setForceRerender(false);
      return;
    }

    const requestId = cacheRequestRef.current + 1;
    cacheRequestRef.current = requestId;
    setIsCheckingCache(true);
    jobsApi.cacheStatus(buildStartJobPayload({
      animationType,
      autoMode,
      durationMax,
      durationMin,
      engine,
      forceReanalyze: false,
      forceRerender: false,
      layout,
      numClips,
      resolution,
      skipSubtitles,
      style,
      url,
    }))
      .then((response) => {
        if (cacheRequestRef.current != requestId) {
          return;
        }
        setCacheStatus(response);
        if (!response.project_cached) {
          setForceReanalyze(false);
          setForceRerender(false);
        }
      })
      .catch(() => {
        if (cacheRequestRef.current != requestId) {
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

  const handleStart = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!url || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setInfoMessage(null);
    try {
      const response = await jobsApi.start(buildStartJobPayload({
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
      if (response.status === 'cached') {
        requestClipsRefresh();
        setInfoMessage(response.message);
      } else if (response.job_id) {
        registerQueuedJob({
          job_id: response.job_id,
          message: response.message,
          style,
          url,
        });
        await fetchJobs();
      }
      setUrl('');
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Job baslatilamadi.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    animationId,
    animationType,
    autoMode,
    durationMax,
    durationMaxId,
    durationMin,
    durationMinId,
    engine,
    engineId,
    error,
    forceReanalyze,
    forceRerender,
    handleStart,
    isCheckingCache,
    infoMessage,
    isSubmitting,
    cacheStatus,
    layout,
    layoutId,
    numClips,
    numClipsId,
    resolution,
    resolutionId,
    setAutoMode,
    setAnimationType,
    setDurationMax,
    setDurationMin,
    setEngine,
    setForceReanalyze,
    setForceRerender,
    setLayout,
    setNumClips,
    setResolution,
    setSkipSubtitles,
    setStyle,
    setUrl,
    skipSubtitles,
    style,
    styleId,
    url,
    urlId,
  };
}
