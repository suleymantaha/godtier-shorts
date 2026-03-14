import { getFreshToken } from '../../../api/client';

export function shouldUseDirectVideoSource(src: string): boolean {
  return src.startsWith('blob:') || src.startsWith('data:') || !src.includes('/api/');
}

export async function fetchProtectedMediaBlob(
  src: string,
  signal: AbortSignal,
): Promise<Blob> {
  const token = await getFreshToken();
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(src, { headers, signal });

  if (!response.ok) {
    throw new Error(`Video fetch failed: ${response.status}`);
  }

  return response.blob();
}

export async function fetchProtectedVideoSource(
  src: string,
  signal: AbortSignal,
): Promise<string> {
  const blob = await fetchProtectedMediaBlob(src, signal);
  return URL.createObjectURL(blob);
}
