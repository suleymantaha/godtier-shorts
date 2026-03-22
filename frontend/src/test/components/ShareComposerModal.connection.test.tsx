import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import {
  mockDeleteCredentials,
  mockGetAccounts,
  mockSaveCredentials,
  renderShareComposerModal,
  resetShareComposerMocks,
} from './shareComposer.test-helpers';

// eslint-disable-next-line max-lines-per-function
describe('ShareComposerModal connection', () => {
  beforeEach(() => {
    resetShareComposerMocks();
    window.history.replaceState({}, '', '/');
  });

  it('connects and disconnects a Postiz account', async () => {
    const user = userEvent.setup();

    mockGetAccounts.mockResolvedValueOnce({ accounts: [], connected: false, connection_mode: 'manual_api_key', provider: 'postiz' });
    mockSaveCredentials.mockResolvedValueOnce({
      accounts: [{ id: 'acc_2', name: 'TikTok Main', platform: 'tiktok', provider: 'tiktok' }],
      provider: 'postiz',
      status: 'connected',
    });

    await renderShareComposerModal();

    await user.type(screen.getByPlaceholderText(/postiz api key/i), '  sk_live_123  ');
    await user.click(screen.getByRole('button', { name: /^bağla$/i }));

    await waitFor(() => {
      expect(mockSaveCredentials).toHaveBeenCalledWith({
        api_key: 'sk_live_123',
        provider: 'postiz',
      });
    });
    expect(await screen.findByText(/postiz hesabı bağlandı/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^kaldır$/i }));

    await waitFor(() => expect(mockDeleteCredentials).toHaveBeenCalled());
    expect(await screen.findByText(/postiz bağlantısı kaldırıldı/i)).toBeInTheDocument();
  });

  it('hides manual api key controls in managed mode and refreshes accounts', async () => {
    const user = userEvent.setup();

    mockGetAccounts.mockResolvedValueOnce({
      accounts: [],
      connected: false,
      connection_mode: 'managed',
      connect_url: '/api/social/oauth/start?integration=youtube&subject_token=test_token',
      provider: 'postiz',
    });
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [{ id: 'acc_3', name: 'YT Managed', platform: 'youtube_shorts', provider: 'youtube' }],
      connected: true,
      connection_mode: 'managed',
      connect_url: '/api/social/oauth/start?integration=youtube&subject_token=test_token',
      provider: 'postiz',
    });

    await renderShareComposerModal();

    expect(await screen.findByText(/manuel api key girişi kapalıdır/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/postiz api key/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^bağla$/i })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /bağlantıyı postiz'de aç/i })).toHaveAttribute(
      'href',
      '/api/social/oauth/start?integration=youtube&subject_token=test_token',
    );

    await user.click(screen.getByRole('button', { name: /hesapları yenile/i }));

    await waitFor(() => expect(mockGetAccounts).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/yt managed/i)).toBeInTheDocument();
  });

  it('auto-refreshes managed connections when the user returns from Postiz', async () => {
    const user = userEvent.setup();

    mockGetAccounts.mockResolvedValueOnce({
      accounts: [],
      connected: false,
      connection_mode: 'managed',
      connect_url: '/api/social/oauth/start?integration=youtube&subject_token=test_token',
      provider: 'postiz',
    });
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [{ id: 'acc_4', name: 'YT Return', platform: 'youtube_shorts', provider: 'youtube' }],
      connected: true,
      connection_mode: 'managed',
      connect_url: '/api/social/oauth/start?integration=youtube&subject_token=test_token',
      provider: 'postiz',
    });

    await renderShareComposerModal();

    await user.click(await screen.findByRole('link', { name: /bağlantıyı postiz'de aç/i }));
    expect(await screen.findByText(/otomatik yenilenecek/i)).toBeInTheDocument();

    await act(async () => {
      window.dispatchEvent(new Event('focus'));
    });

    await waitFor(() => expect(mockGetAccounts).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/postiz hesabı bağlandı/i)).toBeInTheDocument();
    expect(await screen.findByText(/yt return/i)).toBeInTheDocument();
  });
});

describe('ShareComposerModal oauth callback signal', () => {
  beforeEach(() => {
    resetShareComposerMocks();
    window.history.replaceState({}, '', '/');
  });

  it('refreshes accounts from social_oauth callback success signal and clears query', async () => {
    window.history.replaceState({}, '', '/?social_oauth=success');
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [],
      connected: false,
      connection_mode: 'managed',
      connect_url: '/api/social/oauth/start?integration=youtube&subject_token=test_token',
      provider: 'postiz',
    });
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [{ id: 'acc_5', name: 'YT Callback', platform: 'youtube_shorts', provider: 'youtube' }],
      connected: true,
      connection_mode: 'managed',
      connect_url: '/api/social/oauth/start?integration=youtube&subject_token=test_token',
      provider: 'postiz',
    });

    await renderShareComposerModal();

    await waitFor(() => expect(mockGetAccounts).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/postiz hesabı bağlandı/i)).toBeInTheDocument();
    expect(await screen.findByText(/yt callback/i)).toBeInTheDocument();
    expect(window.location.search).toBe('');
  });

  it('shows error from social_oauth callback signal and clears query', async () => {
    window.history.replaceState({}, '', '/?social_oauth=error');
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [],
      connected: false,
      connection_mode: 'managed',
      connect_url: '/api/social/oauth/start?integration=youtube&subject_token=test_token',
      provider: 'postiz',
    });

    await renderShareComposerModal();

    expect(await screen.findByText(/postiz bağlantısı tamamlanamadı/i)).toBeInTheDocument();
    expect(window.location.search).toBe('');
  });
});
