import type { StyleName } from '../../config/subtitleStyles';
import type { Job } from '../../types';

const TERMINAL_JOB_STATUSES = new Set<Job['status']>(['completed', 'cancelled', 'error']);

export interface AutoCutJobStateInput {
  currentJob: Job | null;
  currentJobId: string | null;
  isSubmitting: boolean;
  pendingOutputUrl: string | null;
  requestError: string | null;
}

export interface AutoCutJobStateResult {
  errorMessage: string | null;
  hasTerminalJob: boolean;
  processing: boolean;
  resultUrl: string | null;
}

export interface BuildAutoCutPayloadInput {
  cutAsShort: boolean;
  duration: number;
  endTime: number;
  markers: number[];
  numClips: number;
  skipSubtitles: boolean;
  startTime: number;
  style: StyleName;
}

export interface MarkerAdditionInput {
  currentTime: number;
  endTime: number;
  markers: number[];
  startTime: number;
}

export interface MarkerAdditionResult {
  feedback: string;
  markers: number[];
}

export interface LoadedMetadataRange {
  endTime: number;
  startTime: number;
}

export function deriveAutoCutJobState({
  currentJob,
  currentJobId,
  isSubmitting,
  pendingOutputUrl,
  requestError,
}: AutoCutJobStateInput): AutoCutJobStateResult {
  const hasTerminalJob = Boolean(currentJob?.status && TERMINAL_JOB_STATUSES.has(currentJob.status));
  return {
    errorMessage: resolveAutoCutErrorMessage(currentJob, requestError),
    hasTerminalJob,
    processing: isSubmitting || (Boolean(currentJobId) && !hasTerminalJob),
    resultUrl: resolveAutoCutResultUrl(currentJob, pendingOutputUrl),
  };
}

export function buildAutoCutUploadPayload({
  cutAsShort,
  duration,
  endTime,
  markers,
  numClips,
  skipSubtitles,
  startTime,
  style,
}: BuildAutoCutPayloadInput) {
  const inRange = markers.filter((marker) => marker > startTime && marker < endTime).sort((left, right) => left - right);
  const cutPoints = inRange.length > 0 ? [startTime, ...inRange, endTime] : undefined;
  const useFullVideoForAi = numClips > 1 && !cutPoints && duration > 0;

  return {
    cut_as_short: cutAsShort,
    cut_points: cutPoints,
    end_time: useFullVideoForAi ? duration : endTime,
    num_clips: cutPoints ? cutPoints.length - 1 : numClips,
    skip_subtitles: skipSubtitles,
    start_time: useFullVideoForAi ? 0 : startTime,
    style_name: style,
  };
}

export function getMarkerAdditionResult({
  currentTime,
  endTime,
  markers,
  startTime,
}: MarkerAdditionInput): MarkerAdditionResult {
  const inRange = currentTime > startTime + 0.1 && currentTime < endTime - 0.1;
  if (!inRange) {
    return {
      feedback: 'Once videoyu oynatip kesmek istediginiz zamana gidin.',
      markers,
    };
  }

  const hasNearbyMarker = markers.some((marker) => Math.abs(marker - currentTime) < 0.5);
  if (hasNearbyMarker) {
    return {
      feedback: 'Bu noktada zaten kesim var.',
      markers,
    };
  }

  return {
    feedback: 'Kesim noktasi eklendi.',
    markers: [...markers, currentTime].sort((left, right) => left - right),
  };
}

export function getRangeForLoadedMetadata(mediaDuration: number, previousStart: number, previousEnd: number): LoadedMetadataRange {
  const maxStart = Math.max(0, mediaDuration - 0.5);
  const startTime = Math.max(0, Math.min(previousStart, maxStart));
  const endTime = previousEnd > 0 && previousEnd <= mediaDuration ? previousEnd : Math.min(60, mediaDuration);

  return { endTime, startTime };
}

function resolveAutoCutErrorMessage(currentJob: Job | null, requestError: string | null) {
  if (requestError) {
    return requestError;
  }

  if (currentJob?.status !== 'cancelled' && currentJob?.status !== 'error') {
    return null;
  }

  return currentJob.error ?? currentJob.last_message ?? 'Islem tamamlanamadi.';
}

function resolveAutoCutResultUrl(currentJob: Job | null, pendingOutputUrl: string | null) {
  if (currentJob?.status !== 'completed') {
    return null;
  }

  if (currentJob.output_url) {
    return currentJob.output_url;
  }

  if (currentJob.project_id && currentJob.clip_name) {
    return `/api/projects/${currentJob.project_id}/shorts/${currentJob.clip_name}`;
  }

  return pendingOutputUrl;
}
