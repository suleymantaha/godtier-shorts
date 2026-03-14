import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import {
  mockDeleteCredentials,
  mockGetAccounts,
  mockSaveCredentials,
  renderShareComposerModal,
  resetShareComposerMocks,
} from './shareComposer.test-helpers';

describe('ShareComposerModal connection', () => {
  beforeEach(() => {
    resetShareComposerMocks();
  });

  it('connects and disconnects a Postiz account', async () => {
    const user = userEvent.setup();

    mockGetAccounts.mockResolvedValueOnce({ accounts: [], connected: false, provider: 'postiz' });
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
});
