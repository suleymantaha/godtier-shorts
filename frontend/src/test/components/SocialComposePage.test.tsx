import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import i18n from '../../i18n';
import {
  mockClipsList,
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
    expect(await screen.findByRole('heading', { name: 'Hot Take' })).toBeInTheDocument();
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

  it('lets users pick a clip from the compose tab when no clip query exists', async () => {
    window.history.replaceState({}, '', '/?tab=social-compose');
    mockClipsList.mockResolvedValue({
      clips: [{
        created_at: 777,
        duration: 45,
        has_transcript: true,
        name: 'batch_7_test.mp4',
        project: 'proj_7',
        resolved_project_id: 'proj_7',
        ui_title: 'Batch 7 Test',
        url: '/api/projects/proj_7/files/clip/batch_7_test.mp4',
      }],
    });
    const { SocialComposePage } = await import('../../components/SocialComposePage');
    const user = userEvent.setup();

    render(<SocialComposePage />);

    expect(await screen.findByPlaceholderText(/search clip name or title/i)).toBeInTheDocument();
    await user.click(await screen.findByRole('button', { name: /clip list/i }));
    await user.click(await screen.findByRole('button', { name: /batch 7 test/i }));

    expect(await screen.findByRole('heading', { name: 'Batch 7 Test' })).toBeInTheDocument();
    await waitFor(() => {
      expect(mockGetPrefill).toHaveBeenCalledWith('proj_7', 'batch_7_test.mp4');
      expect(window.location.search).toContain('tab=social-compose');
      expect(window.location.search).toContain('clip_name=batch_7_test.mp4');
    });
  });
});
