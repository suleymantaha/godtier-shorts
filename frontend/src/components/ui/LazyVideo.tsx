import { useRef, useState, useEffect, useCallback, type FC, type RefObject } from 'react';

import type { AppError } from '../../api/errors';
import { useResolvedMediaState } from './protectedMedia';

interface LazyVideoProps {
  src: string;
  poster?: string;
  className?: string;
  muted?: boolean;
  loop?: boolean;
}

export const LazyVideo: FC<LazyVideoProps> = ({ src, poster, className, muted = true, loop = true }) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const visible = useLazyVideoVisibility(wrapperRef);
  const { error, resolvedSrc } = useResolvedMediaState(visible ? src : undefined);
  const videoSrc = resolvedSrc ?? null;

  const handleMouseEnter = useCallback(() => {
    if (!videoRef.current || !videoSrc) return;
    const playPromise = videoRef.current.play();
    if (playPromise instanceof Promise) {
      void playPromise.catch(() => undefined);
    }
  }, [videoSrc]);

  const handleMouseLeave = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
  }, []);

  return (
    <div ref={wrapperRef} className={className}>
      {visible ? (
        <div className="relative h-full w-full">
          <video
            ref={videoRef}
            data-testid="lazy-video"
            src={videoSrc ?? undefined}
            poster={poster}
            className="w-full h-full object-cover"
            preload="metadata"
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            muted={muted}
            loop={loop}
          />
          {error ? <VideoLoadError error={error} /> : null}
        </div>
      ) : (
        <LazyVideoFallback poster={poster} />
      )}
    </div>
  );
};

function useLazyVideoVisibility(wrapperRef: RefObject<HTMLDivElement | null>): boolean {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = wrapperRef.current;
    if (!element) {
      return;
    }

    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) {
        setVisible(true);
        observer.unobserve(element);
      }
    }, { rootMargin: '200px' });

    observer.observe(element);
    return () => observer.disconnect();
  }, [wrapperRef]);

  return visible;
}

function LazyVideoFallback({ poster }: { poster?: string }) {
  if (poster) {
    return <img src={poster} alt="" role="img" className="w-full h-full object-cover" />;
  }

  return <div className="w-full h-full bg-black/40" />;
}

function VideoLoadError({ error }: { error: AppError }) {
  return (
    <div
      role="alert"
      className="absolute inset-x-0 bottom-0 border-t border-red-500/20 bg-black/85 px-3 py-2 text-[11px] font-mono uppercase tracking-wider text-red-100"
    >
      {resolveVideoErrorMessage(error)}
    </div>
  );
}

function resolveVideoErrorMessage(error: AppError): string {
  if (error.code === 'unauthorized') {
    return 'preview auth required';
  }

  if (error.code === 'forbidden') {
    return 'preview access denied';
  }

  if (error.status === 404) {
    return 'preview source missing';
  }

  return 'preview unavailable';
}
