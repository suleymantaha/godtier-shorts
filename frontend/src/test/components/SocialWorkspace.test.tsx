import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import i18n from '../../i18n';

const mockGetProviders = vi.fn();
const mockGetConnections = vi.fn();
const mockGetQueue = vi.fn();
const mockGetCalendar = vi.fn();
const mockGetAnalyticsOverview = vi.fn();
const mockGetAnalyticsAccounts = vi.fn();
const mockGetAnalyticsPosts = vi.fn();
const mockGetPrefill = vi.fn();
const mockStartConnection = vi.fn();
const mockSyncConnections = vi.fn();
const mockDeleteConnection = vi.fn();
const mockPublish = vi.fn();
const mockApproveJob = vi.fn();
const mockCancelJob = vi.fn();
const mockUpdateCalendarItem = vi.fn();
const windowOpenMock = vi.fn();

vi.mock('../../api/client', () => ({
  socialApi: {
    approveJob: (...args: unknown[]) => mockApproveJob(...args),
    cancelJob: (...args: unknown[]) => mockCancelJob(...args),
    deleteConnection: (...args: unknown[]) => mockDeleteConnection(...args),
    getAnalyticsAccounts: (...args: unknown[]) => mockGetAnalyticsAccounts(...args),
    getAnalyticsOverview: (...args: unknown[]) => mockGetAnalyticsOverview(...args),
    getAnalyticsPosts: (...args: unknown[]) => mockGetAnalyticsPosts(...args),
    getCalendar: (...args: unknown[]) => mockGetCalendar(...args),
    getConnections: (...args: unknown[]) => mockGetConnections(...args),
    getPrefill: (...args: unknown[]) => mockGetPrefill(...args),
    getProviders: (...args: unknown[]) => mockGetProviders(...args),
    getQueue: (...args: unknown[]) => mockGetQueue(...args),
    publish: (...args: unknown[]) => mockPublish(...args),
    startConnection: (...args: unknown[]) => mockStartConnection(...args),
    syncConnections: (...args: unknown[]) => mockSyncConnections(...args),
    updateCalendarItem: (...args: unknown[]) => mockUpdateCalendarItem(...args),
  },
}));

function setupMocks() {
  mockGetProviders.mockResolvedValue({
    connection_mode: 'managed',
    providers: [{
      account_count: 1,
      accounts: [{ id: 'acc_yt', name: 'YT Main', platform: 'youtube_shorts', provider: 'youtube' }],
      analytics_supported: true,
      connected: true,
      description: 'YouTube',
      integrations: ['youtube'],
      platform: 'youtube_shorts',
      title: 'YouTube Shorts',
    }],
  });
  mockGetConnections.mockResolvedValue({
    accounts: [{ id: 'acc_yt', name: 'YT Main', platform: 'youtube_shorts', provider: 'youtube' }],
    connected: true,
    providers: [],
  });
  mockGetQueue.mockResolvedValue({ jobs: [] });
  mockGetCalendar.mockResolvedValue({ items: [] });
  mockGetAnalyticsOverview.mockResolvedValue({
    overview: {
      active: 1,
      approval_required: 0,
      connected_accounts: 1,
      failed: 0,
      generated_at: new Date().toISOString(),
      platforms_connected: 1,
      published: 3,
      scheduled: 2,
      total_jobs: 4,
    },
    platforms: [{ active: 1, failed: 0, platform: 'youtube_shorts', published: 3, scheduled: 2, total_jobs: 4 }],
  });
  mockGetAnalyticsAccounts.mockResolvedValue({ accounts: [{ account_id: 'acc_yt', account_name: 'YT Main', active: 1, failed: 0, platform: 'youtube_shorts', published: 3, scheduled: 2, total_jobs: 4 }] });
  mockGetAnalyticsPosts.mockResolvedValue({ posts: [{ account_id: 'acc_yt', account_name: 'YT Main', clip_name: 'clip_1.mp4', failed: 0, latest_at: new Date().toISOString(), latest_state: 'published', platform: 'youtube_shorts', project_id: 'proj_1', published: 1, total_jobs: 1 }] });
  mockGetPrefill.mockResolvedValue({
    clip_exists: true,
    clip_name: 'clip_1.mp4',
    platforms: {
      facebook_reels: { hashtags: ['viral'], text: 'Caption', title: 'Title' },
      instagram_reels: { hashtags: ['viral'], text: 'Caption', title: 'Title' },
      linkedin: { hashtags: ['viral'], text: 'Caption', title: 'Title' },
      tiktok: { hashtags: ['viral'], text: 'Caption', title: 'Title' },
      x: { hashtags: ['viral'], text: 'Caption', title: 'Title' },
      youtube_shorts: { hashtags: ['viral'], text: 'Caption', title: 'Title' },
    },
    project_id: 'proj_1',
    source: { has_clip_metadata: true, has_drafts: false, viral_metadata: null },
  });
  mockStartConnection.mockResolvedValue({ launch_url: 'https://postiz.example/connect', session_id: 'sess_1', status: 'launch_ready' });
  mockSyncConnections.mockResolvedValue({ accounts: [], providers: [], status: 'synced' });
  mockDeleteConnection.mockResolvedValue({ account_id: 'acc_yt', status: 'deleted' });
  mockPublish.mockResolvedValue({ jobs: [], status: 'queued' });
  mockApproveJob.mockResolvedValue({ job_id: 'job_1', status: 'approved' });
  mockCancelJob.mockResolvedValue({ job_id: 'job_1', status: 'cancelled' });
  mockUpdateCalendarItem.mockResolvedValue({ job: { id: 'job_1' }, status: 'updated' });
}

describe('SocialWorkspace', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    setupMocks();
    await i18n.changeLanguage('en');
    window.history.replaceState({}, '', '/?tab=social&project_id=proj_1&clip_name=clip_1.mp4');
    windowOpenMock.mockReset();
    Object.defineProperty(window, 'open', { configurable: true, value: windowOpenMock });
  });

  it('loads social workspace data and opens provider connection in a new tab', async () => {
    const { SocialWorkspace } = await import('../../components/SocialWorkspace');
    const user = userEvent.setup();

    render(<SocialWorkspace />);

    expect(await screen.findByRole('button', { name: /^connect$/i })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^connect$/i }));

    await waitFor(() => {
      expect(mockStartConnection).toHaveBeenCalledWith({ platform: 'youtube_shorts', return_url: window.location.href });
      expect(windowOpenMock).toHaveBeenCalledWith('https://postiz.example/connect', '_blank', 'noopener,noreferrer');
    });
  });

  it('publishes the selected clip with the selected connected account', async () => {
    const { SocialWorkspace } = await import('../../components/SocialWorkspace');
    const user = userEvent.setup();

    render(<SocialWorkspace />);

    expect(await screen.findByDisplayValue('Title')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^publish now$/i }));

    await waitFor(() => {
      expect(mockPublish).toHaveBeenCalledWith(expect.objectContaining({
        clip_name: 'clip_1.mp4',
        mode: 'now',
        project_id: 'proj_1',
        targets: [{ account_id: 'acc_yt', platform: 'youtube_shorts', provider: 'youtube' }],
      }));
    });
  });
});
