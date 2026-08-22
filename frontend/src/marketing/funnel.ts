export const PENDING_PREVIEW_URL_KEY = 'godtier-pending-preview-url';

export function readPendingPreviewUrl(): string {
  return typeof window === 'undefined' ? '' : window.sessionStorage.getItem(PENDING_PREVIEW_URL_KEY) ?? '';
}
