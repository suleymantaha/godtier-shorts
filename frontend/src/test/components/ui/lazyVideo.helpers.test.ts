import { describe, expect, it, vi } from 'vitest';

import * as apiClient from '../../../api/client';
import { fetchProtectedVideoSource, shouldUseDirectVideoSource } from '../../../components/ui/lazyVideo/helpers';

describe('lazyVideo helpers', () => {
  it('detects when a video source can be used directly', () => {
    expect(shouldUseDirectVideoSource('/video.mp4')).toBe(true);
    expect(shouldUseDirectVideoSource('blob:video')).toBe(true);
    expect(shouldUseDirectVideoSource('data:video/mp4;base64,abc')).toBe(true);
    expect(shouldUseDirectVideoSource('http://localhost:8000/api/projects/p1/shorts/c1.mp4')).toBe(false);
  });

  it('fetches protected media with the freshest token', async () => {
    vi.spyOn(apiClient, 'getFreshToken').mockResolvedValue('token-abc');
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => new Blob(['video'], { type: 'video/mp4' }),
    } as Response);
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:protected-video');

    await expect(
      fetchProtectedVideoSource(
        'http://localhost:8000/api/projects/p1/shorts/c1.mp4',
        new AbortController().signal,
      ),
    ).resolves.toBe('blob:protected-video');

    expect(apiClient.getFreshToken).toHaveBeenCalled();
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/projects/p1/shorts/c1.mp4',
      expect.objectContaining({
        headers: { Authorization: 'Bearer token-abc' },
      }),
    );
  });
});
