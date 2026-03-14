import type { Clip, ShareDraftContent, SharePrefillResponse, SocialAccount, SocialPlatform } from '../../types';

export const PLATFORM_LABELS: Record<SocialPlatform, string> = {
  youtube_shorts: 'YouTube Shorts',
  tiktok: 'TikTok',
  instagram_reels: 'Instagram Reels',
  facebook_reels: 'Facebook Reels',
  x: 'X',
  linkedin: 'LinkedIn',
};

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

export function resolveProjectId(clip: Clip | null): string | null {
  return clip?.project && clip.project !== 'legacy' ? clip.project : null;
}

export function localDraftKey(projectId: string, clipName: string): string {
  return `social-share-buffer:${projectId}:${clipName}`;
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
    return 'Takvimli paylaşım onay kuyruğuna alındı.';
  }

  if (mode === 'scheduled') {
    return 'Video Postiz takvimine eklendi.';
  }

  return 'Paylaşım jobları kuyruğa alındı.';
}

export function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
