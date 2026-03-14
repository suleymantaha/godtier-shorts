import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import {
  mockGetPrefill,
  mockPublish,
  renderShareComposerModal,
  resetShareComposerMocks,
} from './shareComposer.test-helpers';

describe('ShareComposerModal publish', () => {
  beforeEach(() => {
    resetShareComposerMocks();
  });

  it('loads prefill and sends publish request with the selected account', async () => {
    const user = userEvent.setup();

    await renderShareComposerModal();

    expect(await screen.findByText(/sosyal paylaşım/i)).toBeInTheDocument();
    await waitFor(() => expect(mockGetPrefill).toHaveBeenCalled());

    expect(screen.getByDisplayValue('TITLE')).toBeInTheDocument();

    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /hemen paylaş/i }));

    await waitFor(() => {
      expect(mockPublish).toHaveBeenCalledWith(
        expect.objectContaining({
          clip_name: 'clip_1.mp4',
          mode: 'now',
          project_id: 'proj_1',
          targets: [{ account_id: 'acc_1', platform: 'youtube_shorts', provider: 'youtube' }],
        }),
      );
    });
  });
});
