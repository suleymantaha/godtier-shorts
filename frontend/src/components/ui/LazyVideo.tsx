import { useRef, useState, useEffect, useCallback } from 'react';
import type { FC } from 'react';

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

  const handleMouseEnter = useCallback(() => {
    videoRef.current?.play();
  }, []);

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
          src={src}
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
