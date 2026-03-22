import { getFreshToken } from '../../../api/client';
import { createAppError } from '../../../api/errors';
import { tSafe } from '../../../i18n';

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
    if (response.status === 401) {
      throw createAppError('unauthorized', tSafe('media.protectedUnauthorized'), {
        source: 'api',
        status: response.status,
      });
    }

    if (response.status === 403) {
      throw createAppError('forbidden', tSafe('media.protectedForbidden'), {
        source: 'api',
        status: response.status,
      });
    }

    if (response.status === 404) {
      throw createAppError('unknown', tSafe('media.protectedMissing'), {
        source: 'api',
        status: response.status,
      });
    }

    throw createAppError('server_unavailable', tSafe('media.protectedLoadFailed'), {
      source: 'api',
      status: response.status,
    });
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
