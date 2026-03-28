import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import i18n from '../../i18n';
import {
  mockClipsList,
  mockGetAccounts,
  mockGetPrefill,
  mockPublish,
  resetShareComposerMocks,
} from './shareComposer.test-helpers';

vi.mock('../../components/ui/protectedMedia', () => ({
  useResolvedMediaState: (src?: string) => ({
    error: null,
    resolvedSrc: src,
  }),
}));

describe('SocialComposePage', () => {
  beforeEach(async () => {
    resetShareComposerMocks();
    Object.defineProperty(HTMLMediaElement.prototype, 'load', {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
      configurable: true,
      value: vi.fn(),
    });
    await i18n.changeLanguage('en');
    window.history.replaceState(
      {},
      '',
      '/social-compose?project_id=proj_1&clip_name=clip_1.mp4',
    );
  });

  it('renders a dedicated preview-first compose page and publishes from it', async () => {
    const { SocialComposePage } = await import('../../components/SocialComposePage');
    const user = userEvent.setup();
    const { container } = render(<SocialComposePage />);

    expect(await screen.findByText(/social composer/i)).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Hot Take' })).toBeInTheDocument();
    expect((await screen.findAllByText('HOOK')).length).toBeGreaterThan(0);
    expect(await screen.findByDisplayValue('Follow for the next part.')).toBeInTheDocument();
    expect(container.querySelector('input[type="datetime-local"]')).toBeNull();
    expect(container.querySelector('video')).not.toBeNull();

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

  it('lets users pick and clear a clip from the compose tab when no clip query exists', async () => {
    window.history.replaceState({}, '', '/social-compose');
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
    const { container } = render(<SocialComposePage />);

    expect(await screen.findByText(/no clip selected yet/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/search clip name or title/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /publish now/i })).toBeDisabled();
    expect(container.querySelector('input[type="datetime-local"]')).toBeNull();

    await user.click(await screen.findByRole('button', { name: /clip list/i }));
    await user.click(await screen.findByRole('button', { name: /batch 7 test/i }));

    expect(await screen.findByRole('heading', { name: 'Batch 7 Test' })).toBeInTheDocument();
    await waitFor(() => {
      expect(mockGetPrefill).toHaveBeenCalledWith('proj_7', 'batch_7_test.mp4');
      expect(window.location.pathname).toBe('/social-compose');
      expect(window.location.search).toContain('clip_name=batch_7_test.mp4');
    });

    expect(screen.getByRole('button', { name: /publish now/i })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: /clip list/i }));
    await user.click(screen.getByRole('button', { name: /clear selection/i }));

    expect(await screen.findByText(/no clip selected yet/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /publish now/i })).toBeDisabled();
    expect(window.location.pathname).toBe('/social-compose');
    expect(window.location.search).toBe('');
  });

  it('refreshes connected accounts from social_connect callback signal and clears the query', async () => {
    window.history.replaceState(
      {},
      '',
      '/social-compose?project_id=proj_1&clip_name=clip_1.mp4&social_connect=success&session_id=sess_1&platform=youtube_shorts',
    );
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [],
      connected: false,
      connection_mode: 'managed',
      connect_url: null,
      provider: 'postiz',
    });
    mockGetAccounts.mockResolvedValueOnce({
      accounts: [{ id: 'acc_yt', name: 'YT Return', platform: 'youtube_shorts', provider: 'youtube' }],
      connected: true,
      connection_mode: 'managed',
      connect_url: null,
      provider: 'postiz',
    });

    const { SocialComposePage } = await import('../../components/SocialComposePage');
    render(<SocialComposePage />);

    expect(await screen.findByText(/postiz account connected\./i)).toBeInTheDocument();
    expect(await screen.findByText(/yt return/i)).toBeInTheDocument();
    expect(window.location.pathname).toBe('/social-compose');
    expect(window.location.search).toBe('?project_id=proj_1&clip_name=clip_1.mp4');
  });
});
