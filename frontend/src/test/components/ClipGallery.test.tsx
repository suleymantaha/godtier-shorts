import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

let mockClipsResponse: { clips: Array<{ name: string; url: string; has_transcript: boolean; created_at: number }> };
let mockShouldReject: boolean;

vi.mock('../../api/client', () => ({
  clipsApi: {
    list: () => {
      if (mockShouldReject) return Promise.reject(new Error('Network error'));
      return Promise.resolve(mockClipsResponse);
    },
  },
}));

vi.mock('../../config', () => ({
  API_BASE: 'http://localhost:8000',
}));

describe('ClipGallery', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockClipsResponse = { clips: [] };
    mockShouldReject = false;
  });

  it('shows loading state initially', async () => {
    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);
    expect(screen.getByText(/scanning|yukleniyor/i)).toBeInTheDocument();
  });

  it('shows empty state when no clips', async () => {
    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);
    const empty = await screen.findByText(/no viral content|icerik yok/i);
    expect(empty).toBeInTheDocument();
  });

  it('shows error state with retry button on fetch failure', async () => {
    mockShouldReject = true;
    const { ClipGallery } = await import('../../components/ClipGallery');
    render(<ClipGallery />);

    const errorEl = await screen.findByRole('alert');
    expect(errorEl).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /tekrar|retry/i });
    expect(retryBtn).toBeInTheDocument();
  });
});
