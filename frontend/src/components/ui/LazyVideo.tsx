import { useRef, useState, useEffect, useCallback, type FC, type RefObject } from 'react';

import { useResolvedMediaSource } from './protectedMedia';

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
  const resolvedSrc = useResolvedMediaSource(visible ? src : undefined) ?? null;

  const handleMouseEnter = useCallback(() => {
    if (!videoRef.current || !resolvedSrc) return;
    const playPromise = videoRef.current.play();
    if (playPromise instanceof Promise) {
      void playPromise.catch(() => undefined);
    }
  }, [resolvedSrc]);

  const handleMouseLeave = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
  }, []);

  return (
    <div ref={wrapperRef} className={className}>
      {visible ? (
        <video
          ref={videoRef}
          data-testid="lazy-video"
          src={resolvedSrc ?? undefined}
          poster={poster}
          className="w-full h-full object-cover"
          preload="metadata"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          muted={muted}
          loop={loop}
        />
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
