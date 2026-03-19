import { useEffect, useState } from 'react';

import { createAppError, isAppError, type AppError } from '../../api/errors';
import { fetchProtectedMediaBlob, fetchProtectedVideoSource, shouldUseDirectVideoSource } from './lazyVideo/helpers';

export function useResolvedMediaSource(src?: string): string | undefined {
  return useResolvedMediaState(src).resolvedSrc;
}

export function useResolvedMediaState(src?: string): { error: AppError | null; resolvedSrc: string | undefined } {
  const [resolvedSource, setResolvedSource] = useState<{ blobSrc: string; src: string } | null>(null);
  const [error, setError] = useState<AppError | null>(null);

  useEffect(() => {
    if (!src) {
      setError(null);
      setResolvedSource(null);
      return;
    }

    if (shouldUseDirectVideoSource(src)) {
      setError(null);
      return;
    }

    let revokeUrl: string | null = null;
    const abortController = new AbortController();
    setError(null);

    void fetchProtectedVideoSource(src, abortController.signal)
      .then((nextBlobSrc) => {
        revokeUrl = nextBlobSrc;
        setResolvedSource({ blobSrc: nextBlobSrc, src });
      })
      .catch((nextError: unknown) => {
        setError(
          isAppError(nextError)
            ? nextError
            : createAppError('server_unavailable', 'Video kaynagi yuklenemedi.'),
        );
      });

    return () => {
      abortController.abort();
      if (revokeUrl) {
        URL.revokeObjectURL(revokeUrl);
      }
    };
  }, [src]);

  if (!src) {
    return {
      error: null,
      resolvedSrc: undefined,
    };
  }

  return {
    error,
    resolvedSrc: shouldUseDirectVideoSource(src)
      ? src
      : (resolvedSource?.src === src ? resolvedSource.blobSrc : undefined),
  };
}

export async function downloadMediaSource(src: string, filename?: string): Promise<void> {
  if (shouldUseDirectVideoSource(src)) {
    triggerDownload(src, filename);
    return;
  }

  const blob = await fetchProtectedMediaBlob(src, new AbortController().signal);
  const blobUrl = URL.createObjectURL(blob);
  triggerDownload(blobUrl, filename);
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 0);
}

export async function openMediaSource(src: string): Promise<void> {
  if (shouldUseDirectVideoSource(src)) {
    openHref(src);
    return;
  }

  const blob = await fetchProtectedMediaBlob(src, new AbortController().signal);
  const blobUrl = URL.createObjectURL(blob);
  openHref(blobUrl);
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}

function triggerDownload(href: string, filename?: string) {
  const link = document.createElement('a');
  link.href = href;
  link.download = filename ?? '';
  link.rel = 'noreferrer';
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function openHref(href: string) {
  const opened = window.open(href, '_blank', 'noopener,noreferrer');
  if (opened) {
    return;
  }

  const link = document.createElement('a');
  link.href = href;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  link.remove();
}
