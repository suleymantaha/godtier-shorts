import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { localDraftKey } from '../../components/shareComposer/helpers';
import {
  createPrefillResponse,
  mockDeleteDrafts,
  mockGetPrefill,
  renderSocialComposePage,
  resetShareComposerMocks,
  shareComposerClip,
} from './shareComposer.test-helpers';

vi.mock('../../components/ui/protectedMedia', () => ({
  useResolvedMediaState: (src?: string) => ({
    error: null,
    resolvedSrc: src,
  }),
}));

const CLIP_QUERY = '/social-compose?project_id=proj_1&clip_name=clip_1.mp4';

describe('SocialComposePage drafts', () => {
  beforeEach(() => {
    resetShareComposerMocks();
    window.history.replaceState({}, '', CLIP_QUERY);
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

    await renderSocialComposePage();

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

    await renderSocialComposePage();

    expect(await screen.findByDisplayValue('LOCAL TITLE')).toBeInTheDocument();
    expect(screen.getByDisplayValue('LOCAL TEXT')).toBeInTheDocument();
    expect(screen.getByDisplayValue('local')).toBeInTheDocument();
  });
});
