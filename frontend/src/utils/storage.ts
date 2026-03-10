/**
 * localStorage'dan güvenli JSON okuma.
 * Parse hatası veya manipüle edilmiş veride fallback döner.
 */
export function readStored<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}
