import type { Clip, ShareDraftContent, SharePrefillResponse, SocialAccount, SocialPlatform } from '../../types';
import { AUTH_IDENTITY_STORAGE_KEY } from '../../auth/isolation';
import { tSafe } from '../../i18n';

export function getPlatformLabel(platform: SocialPlatform): string {
  return tSafe(`shareComposer.platforms.${platform}`, { defaultValue: platform });
}

export const DEFAULT_PLATFORM: SocialPlatform = 'youtube_shorts';

export interface DraftState {
  hasServerDrafts: boolean;
  hasLocalBuffer: boolean;
}

export interface ParsedDraftBuffer {
  buffer: Partial<Record<SocialPlatform, ShareDraftContent>> | null;
  invalid: boolean;
}

export type ShareComposerContentMap = Record<SocialPlatform, ShareDraftContent>;
export type SocialOAuthStatus = 'success' | 'error';
const MANAGED_CONNECT_PENDING_PREFIX = 'social-postiz-managed-connect-pending';

export function resolveProjectId(clip: Clip | null): string | null {
  return clip?.project && clip.project !== 'legacy' ? clip.project : null;
}

export function getShareComposerIdentityScope(): string {
  if (typeof window === 'undefined') {
    return 'anonymous';
  }

  const identity = window.localStorage.getItem(AUTH_IDENTITY_STORAGE_KEY)?.trim();
  return identity || 'anonymous';
}

export function localDraftKey(projectId: string, clipName: string): string {
  return `social-share-buffer:${getShareComposerIdentityScope()}:${projectId}:${clipName}`;
}

export function managedConnectPendingKey(): string {
  return `${MANAGED_CONNECT_PENDING_PREFIX}:${getShareComposerIdentityScope()}`;
}

export function hasManagedConnectPending(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  return window.localStorage.getItem(managedConnectPendingKey()) === '1';
}

export function markManagedConnectPending(): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(managedConnectPendingKey(), '1');
}

export function clearManagedConnectPending(): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.removeItem(managedConnectPendingKey());
}

export function readSocialOAuthStatusFromQuery(search: string): SocialOAuthStatus | null {
  const params = new URLSearchParams(search);
  const status = params.get('social_oauth');
  if (status === 'success' || status === 'error') {
    return status;
  }
  return null;
}

export function clearSocialOAuthStatusQuery(): void {
  if (typeof window === 'undefined') {
    return;
  }

  const currentUrl = new URL(window.location.href);
  if (!currentUrl.searchParams.has('social_oauth')) {
    return;
  }
  currentUrl.searchParams.delete('social_oauth');
  const nextQuery = currentUrl.searchParams.toString();
  const nextUrl = `${currentUrl.pathname}${nextQuery ? `?${nextQuery}` : ''}${currentUrl.hash}`;
  window.history.replaceState({}, '', nextUrl);
}

export function nowPlusHourLocal(now = Date.now()): string {
  const date = new Date(now + 60 * 60 * 1000);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');

  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export function parseLocalDraftBuffer(raw: string | null): ParsedDraftBuffer {
  if (!raw) {
    return { buffer: null, invalid: false };
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { buffer: null, invalid: true };
    }

    return {
      buffer: parsed as Partial<Record<SocialPlatform, ShareDraftContent>>,
      invalid: false,
    };
  } catch {
    return { buffer: null, invalid: true };
  }
}

export function mergeDraftContent(
  serverPlatforms: SharePrefillResponse['platforms'],
  localBuffer: Partial<Record<SocialPlatform, ShareDraftContent>> | null,
): ShareComposerContentMap {
  const merged = { ...serverPlatforms };

  if (!localBuffer) {
    return merged;
  }

  (Object.keys(localBuffer) as SocialPlatform[]).forEach((platform) => {
    const bufferedContent = localBuffer[platform];
    if (!bufferedContent || !merged[platform]) {
      return;
    }

    merged[platform] = { ...merged[platform], ...bufferedContent };
  });

  return merged;
}

export function buildDraftState(
  prefill: SharePrefillResponse,
  localBuffer: Partial<Record<SocialPlatform, ShareDraftContent>> | null,
): DraftState {
  return {
    hasServerDrafts: Boolean(prefill.source?.has_drafts),
    hasLocalBuffer: Boolean(localBuffer && Object.keys(localBuffer).length > 0),
  };
}

export function buildHashtagsFromInput(value: string): string[] {
  return value
    .split(',')
    .map((tag) => tag.trim().replace(/^#/, ''))
    .filter(Boolean);
}

export function toggleSelection(currentValues: string[], nextValue: string): string[] {
  return currentValues.includes(nextValue)
    ? currentValues.filter((value) => value !== nextValue)
    : [...currentValues, nextValue];
}

export function buildPublishTargets(accounts: SocialAccount[], selectedAccountIds: string[]) {
  const selectedIds = new Set(selectedAccountIds);

  return accounts
    .filter((account) => selectedIds.has(account.id))
    .map((account) => ({
      account_id: account.id,
      platform: account.platform,
      provider: account.provider ?? undefined,
    }));
}

export function summarizePublishErrors(errors?: Array<{ error: string }>): string | null {
  if (!errors || errors.length === 0) {
    return null;
  }

  return errors.map((item) => item.error).join(' | ');
}

export function getPublishSuccessMessage(mode: 'now' | 'scheduled', approvalRequired: boolean): string {
  if (mode === 'scheduled' && approvalRequired) {
    return tSafe('shareComposer.publish.scheduledApprovalSuccess');
  }

  if (mode === 'scheduled') {
    return tSafe('shareComposer.publish.scheduledSuccess');
  }

  return tSafe('shareComposer.publish.queuedSuccess');
}

export function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
