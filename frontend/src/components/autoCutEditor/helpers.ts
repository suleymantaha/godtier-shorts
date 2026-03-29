import type { RequestedSubtitleLayout, StyleName, SubtitleAnimationType } from '../../config/subtitleStyles';
import { tSafe } from '../../i18n';
import type { Job } from '../../types';

const TERMINAL_JOB_STATUSES = new Set<Job['status']>(['completed', 'cancelled', 'error', 'review_required']);

export interface AutoCutJobStateInput {
  currentJob: Job | null;
  currentJobId: string | null;
  currentJobMissing: boolean;
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
  animationType: SubtitleAnimationType;
  cutAsShort: boolean;
  duration: number;
  endTime: number;
  layout: RequestedSubtitleLayout;
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
  currentJobMissing,
  isSubmitting,
  pendingOutputUrl,
  requestError,
}: AutoCutJobStateInput): AutoCutJobStateResult {
  const hasTerminalJob = Boolean(currentJob?.status && TERMINAL_JOB_STATUSES.has(currentJob.status));
  return {
    errorMessage: resolveAutoCutErrorMessage(currentJob, requestError),
    hasTerminalJob,
    processing: isSubmitting || (Boolean(currentJobId) && !currentJobMissing && !hasTerminalJob),
    resultUrl: resolveAutoCutResultUrl(currentJob, pendingOutputUrl, { currentJobMissing, isSubmitting }),
  };
}

export function buildAutoCutUploadPayload({
  animationType,
  cutAsShort,
  duration,
  endTime,
  layout,
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
    animation_type: animationType,
    cut_as_short: cutAsShort,
    cut_points: cutPoints,
    end_time: useFullVideoForAi ? duration : endTime,
    layout,
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
      feedback: tSafe('autoCut.markerFeedback.moveToTime'),
      markers,
    };
  }

  const hasNearbyMarker = markers.some((marker) => Math.abs(marker - currentTime) < 0.5);
  if (hasNearbyMarker) {
    return {
      feedback: tSafe('autoCut.markerFeedback.duplicate'),
      markers,
    };
  }

  return {
    feedback: tSafe('autoCut.markerFeedback.added'),
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

  return currentJob.error ?? currentJob.last_message ?? tSafe('autoCut.errors.generic');
}

function resolveAutoCutResultUrl(
  currentJob: Job | null,
  pendingOutputUrl: string | null,
  {
    currentJobMissing,
    isSubmitting,
  }: {
    currentJobMissing: boolean;
    isSubmitting: boolean;
  },
) {
  if (currentJob?.status !== 'completed') {
    return currentJobMissing && !isSubmitting ? pendingOutputUrl : null;
  }

  if (currentJob.output_url) {
    return currentJob.output_url;
  }

  if (currentJob.project_id && currentJob.clip_name) {
    return `/api/projects/${currentJob.project_id}/shorts/${currentJob.clip_name}`;
  }

  return pendingOutputUrl;
}
