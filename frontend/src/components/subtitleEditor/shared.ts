import type { AppErrorCode } from '../../api/errors';
import { tSafe } from '../../i18n';
import type { ClipTranscriptCapabilities } from '../../types';
import { EMPTY_CLIP_TRANSCRIPT_CAPABILITIES } from './helpers';

export const CLIP_RECOVERY_JOB_PREFIX = 'cliprecover_';
export const PROJECT_TRANSCRIPT_JOB_PREFIXES = ['upload_', 'manualcut_', 'projecttranscript_'];
export const AUTH_BOOTSTRAP_RECOVERY_MS = 2500;
export const TRUSTED_CLIP_TRANSCRIPT_RETRY_ATTEMPTS = 2;

export function getClipRecoverySuccessMessage(): string {
  return tSafe('subtitleEditor.transcript.transcriptLoaded', {
    defaultValue: 'Clip transcript loaded.',
  });
}

export function getProjectTranscriptSuccessMessage(): string {
  return tSafe('subtitleEditor.transcript.projectTranscriptReady', {
    defaultValue: 'Project transcript ready.',
  });
}

export function getReburnWarningMessage(): string {
  return tSafe('subtitleEditor.transcript.reburnWarningMessage', {
    defaultValue: 'Raw video is missing. If subtitles are already burned into the video, reburn may apply subtitles a second time.',
  });
}

export function getTrustedClipTranscriptMismatchMessage(): string {
  return tSafe('subtitleEditor.transcript.mismatchFallback', {
    defaultValue: 'This clip appears transcript-ready in Clip Library, but the detailed transcript could not be verified yet.',
  });
}

export const AUTH_BLOCKING_CODES = new Set<AppErrorCode>([
  'auth_provider_unavailable',
  'auth_revalidation_required',
  'forbidden',
  'token_expired',
  'unauthorized',
]);

export type ProjectsFetchStatus = 'good' | 'degraded' | 'unknown';
export type SubtitleSourceState = 'loading' | 'ready' | 'auth_blocked';
export type TranscriptAccessState = 'idle' | 'loading' | 'ready' | 'auth_blocked' | 'mismatch';

export class TrustedReadyClipMismatchError extends Error {
  constructor() {
    super(getTrustedClipTranscriptMismatchMessage());
    this.name = 'TrustedReadyClipMismatchError';
  }
}

export function normalizeCapabilities(
  capabilities?: ClipTranscriptCapabilities,
): ClipTranscriptCapabilities {
  return { ...EMPTY_CLIP_TRANSCRIPT_CAPABILITIES, ...capabilities };
}

export function isProjectTranscriptJob(jobId: string): boolean {
  return PROJECT_TRANSCRIPT_JOB_PREFIXES.some((prefix) => jobId.startsWith(prefix));
}
