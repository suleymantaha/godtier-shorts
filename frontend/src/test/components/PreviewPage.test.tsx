import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../../i18n';

const analyzeMock = vi.fn();

vi.mock('../../api/preview', () => ({
  previewApi: { analyze: (...args: unknown[]) => analyzeMock(...args) },
}));

vi.mock('../../components/security/TurnstileGate', () => ({
  TurnstileGate: ({ onToken }: { onToken: (token: string) => void }) => (
    <button type="button" onClick={() => onToken('turnstile-token')}>Verify human</button>
  ),
}));

describe('PreviewPage', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('tr');
    analyzeMock.mockReset();
    analyzeMock.mockResolvedValue({
      source: { video_id: 'abc', title: 'Test video', duration_seconds: 120, thumbnail_url: null },
      transcript: [{ start: 0, end: 20, text: 'Guclu bir an' }],
      transcript_source: 'captions',
      preview_mode: 'browser',
      candidates: [
        { start_time: 0, end_time: 20, ui_title: 'Birinci aday', hook_text: 'Hook', viral_score: 91 },
        { start_time: 20, end_time: 40, ui_title: 'Ikinci aday', hook_text: 'Hook 2', viral_score: 85 },
      ],
    });
  });

  it('submits a YouTube URL and renders browser-only candidate timestamps', async () => {
    const { PreviewPage } = await import('../../components/PreviewPage');
    const user = userEvent.setup();
    render(<PreviewPage />);

    await user.type(screen.getByLabelText('YouTube video URL'), 'https://youtu.be/abc123DEF45');
    await user.click(screen.getByRole('button', { name: 'Verify human' }));
    await user.click(screen.getByRole('button', { name: 'Ücretsiz analiz et' }));

    expect(await screen.findByText('Birinci aday')).toBeInTheDocument();
    expect(screen.getByText('00:00 – 00:20')).toBeInTheDocument();
    expect(screen.getByText('Ikinci aday')).toBeInTheDocument();
    expect(analyzeMock).toHaveBeenCalledWith('https://youtu.be/abc123DEF45', 'turnstile-token');
    expect(screen.queryByRole('video')).not.toBeInTheDocument();
  });
});
