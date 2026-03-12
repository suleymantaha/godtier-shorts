import { useRef, useState, useEffect, useCallback } from 'react';
import type { FC } from 'react';
import { getFreshToken } from '../../api/client';

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
  const [visible, setVisible] = useState(false);
  const [resolvedSrc, setResolvedSrc] = useState<string | null>(null);

  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.unobserve(el);
        }
      },
      { rootMargin: '200px' },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) {
      return;
    }

    const usesProtectedApi = src.includes('/api/');
    if (!usesProtectedApi || src.startsWith('blob:') || src.startsWith('data:')) {
      setResolvedSrc(src);
      return;
    }

    let revokedUrl: string | null = null;
    const abortController = new AbortController();

    void (async () => {
      try {
        const token = await getFreshToken();
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        const response = await fetch(src, {
          headers,
          signal: abortController.signal,
        });
        if (!response.ok) {
          throw new Error(`Video fetch failed: ${response.status}`);
        }
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        revokedUrl = blobUrl;
        setResolvedSrc(blobUrl);
      } catch {
        setResolvedSrc(null);
      }
    })();

    return () => {
      abortController.abort();
      if (revokedUrl) {
        URL.revokeObjectURL(revokedUrl);
      }
    };
  }, [visible, src]);

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
        poster ? (
          <img src={poster} alt="" role="img" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full bg-black/40" />
        )
      )}
    </div>
  );
};
