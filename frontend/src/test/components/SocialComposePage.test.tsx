import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import i18n from '../../i18n';
import {
  mockGetPrefill,
  mockPublish,
  resetShareComposerMocks,
} from './shareComposer.test-helpers';

describe('SocialComposePage', () => {
  beforeEach(async () => {
    resetShareComposerMocks();
    await i18n.changeLanguage('en');
    window.history.replaceState(
      {},
      '',
      '/?tab=social-compose&project_id=proj_1&clip_name=clip_1.mp4&clip_url=%2Fapi%2Fprojects%2Fproj_1%2Ffiles%2Fclip%2Fclip_1.mp4&clip_title=Hot%20Take&clip_created_at=123&clip_duration=75',
    );
  });

  it('renders a dedicated preview-first compose page and publishes from it', async () => {
    const { SocialComposePage } = await import('../../components/SocialComposePage');
    const user = userEvent.setup();

    render(<SocialComposePage />);

    expect(await screen.findByText(/social composer/i)).toBeInTheDocument();
    expect(await screen.findByText('Hot Take')).toBeInTheDocument();
    expect((await screen.findAllByText('HOOK')).length).toBeGreaterThan(0);
    expect(await screen.findByDisplayValue('Follow for the next part.')).toBeInTheDocument();

    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /publish now/i }));

    await waitFor(() => {
      expect(mockGetPrefill).toHaveBeenCalledWith('proj_1', 'clip_1.mp4');
      expect(mockPublish).toHaveBeenCalledWith(expect.objectContaining({
        clip_name: 'clip_1.mp4',
        mode: 'now',
        project_id: 'proj_1',
      }));
    });
  });
});
