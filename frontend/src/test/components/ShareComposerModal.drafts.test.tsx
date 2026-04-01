import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import { localDraftKey } from '../../components/shareComposer/helpers';
import {
  createPrefillResponse,
  mockDeleteDrafts,
  mockGetPrefill,
  renderShareComposerModal,
  resetShareComposerMocks,
  shareComposerClip,
} from './shareComposer.test-helpers';

describe('ShareComposerModal drafts', () => {
  beforeEach(() => {
    resetShareComposerMocks();
  });

  it('clears stale drafts and reloads the AI suggestion', async () => {
    const user = userEvent.setup();

    mockGetPrefill
      .mockResolvedValueOnce(createPrefillResponse({
        hasDrafts: true,
        hashtags: ['old'],
        text: 'OLD TEXT',
        title: 'OLD TITLE',
      }))
      .mockResolvedValueOnce(createPrefillResponse());

    await renderShareComposerModal();

    expect(await screen.findByText(/a saved share draft was loaded/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /return to ai suggestion/i }));

    await waitFor(() => {
      expect(mockDeleteDrafts).toHaveBeenCalledWith('proj_1', 'clip_1.mp4');
      expect(screen.getByDisplayValue('TITLE')).toBeInTheDocument();
    });
  });

  it('prefers the local draft buffer over the server suggestion', async () => {
    window.localStorage.setItem(localDraftKey(shareComposerClip.project!, shareComposerClip.name), JSON.stringify({
      youtube_shorts: { hashtags: ['local'], text: 'LOCAL TEXT', title: 'LOCAL TITLE' },
    }));

    await renderShareComposerModal();

    expect(await screen.findByDisplayValue('LOCAL TITLE')).toBeInTheDocument();
    expect(screen.getByDisplayValue('LOCAL TEXT')).toBeInTheDocument();
    expect(screen.getByDisplayValue('local')).toBeInTheDocument();
  });
});
