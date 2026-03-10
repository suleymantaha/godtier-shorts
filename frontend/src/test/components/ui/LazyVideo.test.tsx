import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LazyVideo } from '../../../components/ui/LazyVideo';

let observeCallback: IntersectionObserverCallback;

const mockObserve = vi.fn();
const mockUnobserve = vi.fn();
const mockDisconnect = vi.fn();

beforeEach(() => {
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

  it('mounts video element after intersection', () => {
    const { container } = render(<LazyVideo src="/video.mp4" poster="/thumb.jpg" />);
    const wrapper = container.firstElementChild!;

    act(() => {
      observeCallback(
        [{ isIntersecting: true, target: wrapper } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    });

    const video = container.querySelector('video');
    expect(video).toBeTruthy();
    expect(video!.getAttribute('src')).toBe('/video.mp4');
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
});
