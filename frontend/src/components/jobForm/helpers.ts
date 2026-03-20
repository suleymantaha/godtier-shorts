import {
  ANIMATION_SELECT_OPTIONS,
  isStyleName,
  isSubtitleAnimationType,
  type RequestedSubtitleLayout,
  STYLE_LABELS,
  STYLE_OPTIONS,
  type StyleName,
  type SubtitleAnimationType,
} from '../../config/subtitleStyles';
import type { StartJobPayload } from '../../types';
import { readStored } from '../../utils/storage';

export const JOB_FORM_PREFS_STORAGE_KEY = 'godtier-job-form-preferences';
export const DEFAULT_ENGINE = 'local';
export const DEFAULT_AUTO_DURATION_RANGE = { max: 180, min: 120 } as const;
export const CLIP_COUNT_LIMITS = { max: 20, min: 1 } as const;
export const DURATION_LIMITS = { max: 300, min: 30 } as const;
export const ENGINE_OPTIONS = new Set(['local', 'lmstudio', 'cloud']);
export const ENGINE_SELECT_OPTIONS = [
  { label: 'Local (Ollama)', value: 'local' },
  { label: 'Local (LM Studio)', value: 'lmstudio' },
  { label: 'Cloud (OpenAI API)', value: 'cloud' },
];
export const RESOLUTION_OPTIONS = [
  { label: 'En Iyi', value: 'best' },
  { label: '1080p', value: '1080p' },
  { label: '720p', value: '720p' },
  { label: '480p', value: '480p' },
];
export const LAYOUT_SELECT_OPTIONS = [
  { label: 'Auto', value: 'auto' },
  { label: 'Single', value: 'single' },
  { label: 'Split', value: 'split' },
];
export const STYLE_SELECT_OPTIONS = STYLE_OPTIONS.map((style) => ({
  label: STYLE_LABELS[style],
  value: style,
}));
export const MOTION_SELECT_OPTIONS = ANIMATION_SELECT_OPTIONS;

interface JobFormPrefs {
  animationType?: SubtitleAnimationType;
  engine?: string;
  layout?: RequestedSubtitleLayout;
  style?: StyleName;
}

interface BuildStartJobPayloadInput {
  animationType: SubtitleAnimationType;
  autoMode: boolean;
  durationMax: number;
  durationMin: number;
  engine: string;
  forceReanalyze?: boolean;
  forceRerender?: boolean;
  layout: RequestedSubtitleLayout;
  numClips: number;
  resolution: string;
  skipSubtitles: boolean;
  style: StyleName;
  url: string;
}

export function readInitialEngine(): string {
  const stored = readStored<JobFormPrefs>(JOB_FORM_PREFS_STORAGE_KEY, { engine: DEFAULT_ENGINE });
  const candidate = (stored.engine ?? DEFAULT_ENGINE).toLowerCase();

  return ENGINE_OPTIONS.has(candidate) ? candidate : DEFAULT_ENGINE;
}

export function readInitialStyle(): StyleName {
  const stored = readStored<JobFormPrefs>(JOB_FORM_PREFS_STORAGE_KEY, { style: 'TIKTOK' });
  return isStyleName(stored.style) ? stored.style : 'TIKTOK';
}

export function readInitialAnimationType(): SubtitleAnimationType {
  const stored = readStored<JobFormPrefs>(JOB_FORM_PREFS_STORAGE_KEY, { animationType: 'default' });
  return isSubtitleAnimationType(stored.animationType) ? stored.animationType : 'default';
}

export function readInitialLayout(): RequestedSubtitleLayout {
  const stored = readStored<JobFormPrefs>(JOB_FORM_PREFS_STORAGE_KEY, { layout: 'auto' });
  return stored.layout === 'single' || stored.layout === 'split' || stored.layout === 'auto' ? stored.layout : 'auto';
}

export function clampClipCount(value: number): number {
  return clampNumber(value, CLIP_COUNT_LIMITS.min, CLIP_COUNT_LIMITS.max, CLIP_COUNT_LIMITS.min);
}

export function clampDurationSeconds(value: number): number {
  return clampNumber(value, DURATION_LIMITS.min, DURATION_LIMITS.max, DURATION_LIMITS.min);
}

export function resolveDurationRange(autoMode: boolean, durationMin: number, durationMax: number) {
  if (autoMode) {
    return DEFAULT_AUTO_DURATION_RANGE;
  }

  return {
    max: clampDurationSeconds(durationMax),
    min: clampDurationSeconds(durationMin),
  };
}

export function buildStartJobPayload({
  animationType,
  autoMode,
  durationMax,
  durationMin,
  engine,
  forceReanalyze = false,
  forceRerender = false,
  layout,
  numClips,
  resolution,
  skipSubtitles,
  style,
  url,
}: BuildStartJobPayloadInput): StartJobPayload {
  const resolvedDuration = resolveDurationRange(autoMode, durationMin, durationMax);

  return {
    ai_engine: engine,
    animation_type: animationType,
    auto_mode: autoMode,
    duration_max: resolvedDuration.max,
    duration_min: resolvedDuration.min,
    force_reanalyze: forceReanalyze,
    force_rerender: forceRerender,
    layout,
    num_clips: clampClipCount(numClips),
    resolution,
    skip_subtitles: skipSubtitles,
    style_name: style,
    youtube_url: url,
  };
}

function clampNumber(value: number, min: number, max: number, fallback: number): number {
  const safeValue = Number.isFinite(value) ? value : fallback;

  return Math.min(max, Math.max(min, safeValue));
}
