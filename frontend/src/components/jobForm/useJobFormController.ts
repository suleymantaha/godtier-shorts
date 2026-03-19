import { useEffect, useId, useState, type FormEvent } from 'react';

import { jobsApi } from '../../api/client';
import type { RequestedSubtitleLayout, StyleName, SubtitleAnimationType } from '../../config/subtitleStyles';
import { useJobStore } from '../../store/useJobStore';
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
  const [error, setError] = useState<string | null>(null);
  const { fetchJobs } = useJobStore();

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
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(JOB_FORM_PREFS_STORAGE_KEY, JSON.stringify({ animationType, engine, layout, style }));
    }
  }, [animationType, engine, layout, style]);

  const handleStart = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!url || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await jobsApi.start(buildStartJobPayload({ animationType, autoMode, durationMax, durationMin, engine, layout, numClips, resolution, skipSubtitles, style, url }));
      await fetchJobs();
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
    handleStart,
    isSubmitting,
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
