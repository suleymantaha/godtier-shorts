import { render, screen, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LazyVideo } from '../../../components/ui/LazyVideo';
import * as apiClient from '../../../api/client';

let observeCallback: IntersectionObserverCallback;

const mockObserve = vi.fn();
const mockUnobserve = vi.fn();
const mockDisconnect = vi.fn();

beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal('IntersectionObserver', class {
    constructor(cb: IntersectionObserverCallback) {
      observeCallback = cb;
    }
    observe = mockObserve;
    unobserve = mockUnobserve;
    disconnect = mockDisconnect;
  });
});

describe('LazyVideo', () => {
  it('renders a poster placeholder before intersection', () => {
    render(<LazyVideo src="/video.mp4" poster="/thumb.jpg" className="my-cls" />);
    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('src', '/thumb.jpg');
    expect(screen.queryByTestId('lazy-video')).toBeNull();
  });

  it('mounts video element after intersection', async () => {
    const { container } = render(<LazyVideo src="/video.mp4" poster="/thumb.jpg" />);
    const wrapper = container.firstElementChild!;

    act(() => {
      observeCallback(
        [{ isIntersecting: true, target: wrapper } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    });

    await waitFor(() => {
      const video = container.querySelector('video');
      expect(video).toBeTruthy();
      expect(video!.getAttribute('src')).toBe('/video.mp4');
    });
  });

  it('calls unobserve after becoming visible', () => {
    const { container } = render(<LazyVideo src="/video.mp4" poster="/thumb.jpg" />);
    const wrapper = container.firstElementChild!;

    act(() => {
      observeCallback(
        [{ isIntersecting: true, target: wrapper } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    });

    expect(mockUnobserve).toHaveBeenCalled();
  });

  it('fetches protected api videos with auth and uses blob URL', async () => {
    const tokenSpy = vi.spyOn(apiClient, 'getFreshToken').mockResolvedValue('token-123');
    const blob = new Blob(['video'], { type: 'video/mp4' });
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => blob,
    } as Response);
    const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:video-auth');

    const { container } = render(<LazyVideo src="http://localhost:8000/api/projects/p1/shorts/c1.mp4" />);
    const wrapper = container.firstElementChild!;

    act(() => {
      observeCallback(
        [{ isIntersecting: true, target: wrapper } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    });

    await waitFor(() => {
      const video = container.querySelector('video');
      expect(video).toBeTruthy();
      expect(video!.getAttribute('src')).toBe('blob:video-auth');
    });

    expect(tokenSpy).toHaveBeenCalled();
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/projects/p1/shorts/c1.mp4',
      expect.objectContaining({
        headers: { Authorization: 'Bearer token-123' },
      }),
    );
    expect(createObjectURLSpy).toHaveBeenCalled();
  });
});
