import { API_BASE } from '../config';

/**
 * Clip URL'ini güvenli şekilde oluşturur.
 * clip.url path ise API_BASE ile birleştirir; http/https ile başlıyorsa olduğu gibi döner.
 */
export function getClipUrl(clip: { url: string }): string {
  if (clip.url.startsWith('http')) return clip.url;
  return `${API_BASE}${clip.url.startsWith('/') ? '' : '/'}${clip.url}`;
}
