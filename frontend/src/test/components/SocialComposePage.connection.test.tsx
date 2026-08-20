import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  mockDeleteCredentials,
  mockGetAccounts,
  mockSaveCredentials,
  mockStartConnection,
  renderSocialComposePage,
  resetShareComposerMocks,
} from './shareComposer.test-helpers';

vi.mock('../../components/ui/protectedMedia', () => ({
  useResolvedMediaState: (src?: string) => ({
    error: null,
    resolvedSrc: src,
  }),
}));

const CLIP_QUERY = '/social-compose?project_id=proj_1&clip_name=clip_1.mp4';

describe('SocialComposePage connection', () => {
  beforeEach(() => {
    resetShareComposerMocks();
    window.history.replaceState({}, '', CLIP_QUERY);
  });

  it('connects and disconnects a Postiz account in manual API key mode', async () => {
    const user = userEvent.setup();

    mockGetAccounts.mockResolvedValueOnce({ accounts: [], connected: false, connection_mode: 'manual_api_key', provider: 'postiz' });
    mockSaveCredentials.mockResolvedValueOnce({
      accounts: [{ id: 'acc_2', name: 'TikTok Main', platform: 'tiktok', provider: 'tiktok' }],
      provider: 'postiz',
      status: 'connected',
    });

    await renderSocialComposePage();

    await user.type(await screen.findByPlaceholderText(/postiz api key/i), '  sk_live_123  ');
    await user.click(screen.getByRole('button', { name: /^connect$/i }));

    await waitFor(() => {
      expect(mockSaveCredentials).toHaveBeenCalledWith({
        api_key: 'sk_live_123',
        provider: 'postiz',
      });
    });
    expect(await screen.findByText(/postiz account connected\./i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^remove$/i }));

    await waitFor(() => expect(mockDeleteCredentials).toHaveBeenCalled());
    expect(await screen.findByText(/postiz connection removed\./i)).toBeInTheDocument();
  });

  it('hides the manual API key connector in managed mode', async () => {
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [],
      connected: false,
      connection_mode: 'managed',
      connect_url: null,
      provider: 'postiz',
    });

    await renderSocialComposePage();

    await screen.findByRole('heading', { name: 'Hot Take' });
    expect(screen.queryByPlaceholderText(/postiz api key/i)).not.toBeInTheDocument();
  });

  it('auto-refreshes managed connections when the user returns from Postiz', async () => {
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [],
      connected: false,
      connection_mode: 'managed',
      connect_url: null,
      provider: 'postiz',
    });
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [{ id: 'acc_4', name: 'YT Return', platform: 'youtube_shorts', provider: 'youtube' }],
      connected: true,
      connection_mode: 'managed',
      connect_url: null,
      provider: 'postiz',
    });

    const user = userEvent.setup();
    await renderSocialComposePage();

    await user.click(await screen.findByRole('button', { name: /connect accounts/i }));
    await waitFor(() => expect(mockStartConnection).toHaveBeenCalled());

    await act(async () => {
      window.dispatchEvent(new Event('focus'));
    });

    await waitFor(() => expect(mockGetAccounts).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/postiz account connected\./i)).toBeInTheDocument();
    expect(await screen.findByText(/yt return/i)).toBeInTheDocument();
  });
});

describe('SocialComposePage oauth callback signal', () => {
  beforeEach(() => {
    resetShareComposerMocks();
  });

  it('refreshes accounts from social_oauth callback success signal and clears the status query', async () => {
    window.history.replaceState({}, '', `${CLIP_QUERY}&social_oauth=success`);
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [],
      connected: false,
      connection_mode: 'managed',
      connect_url: null,
      provider: 'postiz',
    });
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [{ id: 'acc_5', name: 'YT Callback', platform: 'youtube_shorts', provider: 'youtube' }],
      connected: true,
      connection_mode: 'managed',
      connect_url: null,
      provider: 'postiz',
    });

    await renderSocialComposePage();

    await waitFor(() => expect(mockGetAccounts).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/postiz account connected\./i)).toBeInTheDocument();
    expect(await screen.findByText(/yt callback/i)).toBeInTheDocument();
    expect(window.location.search).not.toContain('social_oauth');
  });

  it('shows an error from the social_oauth callback error signal and clears the status query', async () => {
    window.history.replaceState({}, '', `${CLIP_QUERY}&social_oauth=error`);
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [],
      connected: false,
      connection_mode: 'managed',
      connect_url: null,
      provider: 'postiz',
    });

    await renderSocialComposePage();

    expect(await screen.findByText(/postiz connection could not be completed\./i)).toBeInTheDocument();
    expect(window.location.search).not.toContain('social_oauth');
  });
});
