import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as apiClient from '../../../api/client';
import { useResolvedMediaSource } from '../../../components/ui/protectedMedia';

function TestResolvedMedia({ src }: { src?: string }) {
  const resolvedSrc = useResolvedMediaSource(src);
  return <div data-testid="resolved-src">{resolvedSrc ?? 'pending'}</div>;
}

describe('protectedMedia', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns direct media sources without fetching', () => {
    const fetchSpy = vi.spyOn(global, 'fetch');

    render(<TestResolvedMedia src="blob:local-video" />);

    expect(screen.getByTestId('resolved-src')).toHaveTextContent('blob:local-video');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('resolves protected api media to a blob URL', async () => {
    vi.spyOn(apiClient, 'getFreshToken').mockResolvedValue('token-abc');
    vi.spyOn(global, 'fetch').mockResolvedValue({
      blob: async () => new Blob(['video'], { type: 'video/mp4' }),
      ok: true,
      status: 200,
    } as Response);
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:resolved-video');

    render(<TestResolvedMedia src="http://localhost:8000/api/projects/p1/shorts/c1.mp4" />);

    await waitFor(() => {
      expect(screen.getByTestId('resolved-src')).toHaveTextContent('blob:resolved-video');
    });

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/projects/p1/shorts/c1.mp4',
      expect.objectContaining({
        headers: { Authorization: 'Bearer token-abc' },
      }),
    );
  });
});
