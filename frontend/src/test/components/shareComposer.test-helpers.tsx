import { render } from '@testing-library/react';
import { vi } from 'vitest';

import type { Clip, ShareDraftContent, SharePrefillResponse, SocialPlatform } from '../../types';

export const mockGetAccounts = vi.fn();
export const mockGetPrefill = vi.fn();
export const mockGetPublishJobs = vi.fn();
export const mockPublish = vi.fn();
export const mockSaveDrafts = vi.fn();
export const mockDeleteDrafts = vi.fn();
export const mockSaveCredentials = vi.fn();
export const mockDeleteCredentials = vi.fn();
export const mockApproveJob = vi.fn();
export const mockCancelJob = vi.fn();

vi.mock('../../api/client', () => ({
  socialApi: {
    approveJob: (...args: unknown[]) => mockApproveJob(...args),
    cancelJob: (...args: unknown[]) => mockCancelJob(...args),
    deleteCredentials: (...args: unknown[]) => mockDeleteCredentials(...args),
    deleteDrafts: (...args: unknown[]) => mockDeleteDrafts(...args),
    getAccounts: (...args: unknown[]) => mockGetAccounts(...args),
    getPrefill: (...args: unknown[]) => mockGetPrefill(...args),
    getPublishJobs: (...args: unknown[]) => mockGetPublishJobs(...args),
    publish: (...args: unknown[]) => mockPublish(...args),
    saveCredentials: (...args: unknown[]) => mockSaveCredentials(...args),
    saveDrafts: (...args: unknown[]) => mockSaveDrafts(...args),
  },
}));

export const shareComposerClip: Clip = {
  created_at: Date.now(),
  has_transcript: true,
  name: 'clip_1.mp4',
  project: 'proj_1',
  url: '/api/projects/proj_1/files/clip/clip_1.mp4',
};

function buildPlatforms(title: string, text: string, hashtags: string[], hookText: string, ctaText: string): Record<SocialPlatform, ShareDraftContent> {
  return {
    facebook_reels: { cta_text: ctaText, hashtags, hook_text: hookText, text, title },
    instagram_reels: { cta_text: ctaText, hashtags, hook_text: hookText, text, title },
    linkedin: { cta_text: ctaText, hashtags, hook_text: hookText, text, title },
    tiktok: { cta_text: ctaText, hashtags, hook_text: hookText, text, title },
    x: { cta_text: ctaText, hashtags, hook_text: hookText, text, title },
    youtube_shorts: { cta_text: ctaText, hashtags, hook_text: hookText, text, title },
  };
}

export function createPrefillResponse({
  hasDrafts = false,
  hashtags = ['viral'],
  hookText = 'HOOK',
  text = 'TEXT',
  title = 'TITLE',
  ctaText = 'Follow for the next part.',
}: {
  ctaText?: string;
  hasDrafts?: boolean;
  hashtags?: string[];
  hookText?: string;
  text?: string;
  title?: string;
} = {}): SharePrefillResponse {
  return {
    clip_exists: true,
    clip_name: shareComposerClip.name,
    platforms: buildPlatforms(title, text, hashtags, hookText, ctaText),
    project_id: shareComposerClip.project!,
    source: { has_clip_metadata: true, has_drafts: hasDrafts, viral_metadata: null },
  };
}

export function resetShareComposerMocks() {
  vi.clearAllMocks();
  window.localStorage.clear();

  mockGetAccounts.mockResolvedValue({
    accounts: [{ id: 'acc_1', name: 'Main YT', platform: 'youtube_shorts', provider: 'youtube' }],
    connected: true,
    connection_mode: 'manual_api_key',
    connect_url: null,
    provider: 'postiz',
  });
  mockGetPrefill.mockResolvedValue(createPrefillResponse());
  mockGetPublishJobs.mockResolvedValue({ jobs: [] });
  mockPublish.mockResolvedValue({ jobs: [], status: 'queued' });
  mockSaveDrafts.mockResolvedValue({ status: 'saved' });
  mockDeleteDrafts.mockResolvedValue({ deleted: 6, status: 'deleted' });
  mockSaveCredentials.mockResolvedValue({ accounts: [], provider: 'postiz', status: 'connected' });
  mockDeleteCredentials.mockResolvedValue({ provider: 'postiz', status: 'deleted' });
  mockApproveJob.mockResolvedValue({ status: 'approved' });
  mockCancelJob.mockResolvedValue({ status: 'cancelled' });
}

export async function renderShareComposerModal(
  overrides: Partial<{ clip: Clip | null; onClose: () => void; open: boolean }> = {},
) {
  const { ShareComposerModal } = await import('../../components/ShareComposerModal');

  return render(
    <ShareComposerModal
      clip={overrides.clip ?? shareComposerClip}
      onClose={overrides.onClose ?? vi.fn()}
      open={overrides.open ?? true}
    />,
  );
}
