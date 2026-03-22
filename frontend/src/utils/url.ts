import { API_BASE } from '../config';

/**
 * Clip URL'ini güvenli şekilde oluşturur.
 * clip.url path ise API_BASE ile birleştirir; http/https ile başlıyorsa olduğu gibi döner.
 */
export function getClipUrl(
  clip: { url: string },
  options?: { cacheBust?: number | string | null | undefined },
): string {
  const baseUrl = resolveApiUrl(clip.url);

  const cacheBust = options?.cacheBust;
  if (cacheBust === null || cacheBust === undefined || cacheBust === '') {
    return baseUrl;
  }

  const separator = baseUrl.includes('?') ? '&' : '?';
  return `${baseUrl}${separator}t=${encodeURIComponent(String(cacheBust))}`;
}

export function resolveApiUrl(url: string): string {
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }

  return `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`;
}
