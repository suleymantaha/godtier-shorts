/**
 * frontend/src/config.ts
 * ========================
 * Merkezi URL sabitleri.
 * API URL'ini değiştirmek istersen sadece bu dosyayı düzenle
 * veya .env.local dosyasında VITE_API_URL değişkenini ayarla.
 */

const envUrl = import.meta.env.VITE_API_URL as string | undefined;
if (import.meta.env.PROD && !envUrl) {
  console.warn('VITE_API_URL not set in production');
}
export const API_BASE = envUrl ?? 'http://localhost:8000';
export const WS_BASE = API_BASE.replace(/^http/, 'ws');
export const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined) ?? '';
export const CLERK_JWT_TEMPLATE = (import.meta.env.VITE_CLERK_JWT_TEMPLATE as string | undefined) ?? '';

export const MAX_UPLOAD_BYTES = Number((import.meta.env.VITE_MAX_UPLOAD_BYTES as string | undefined) ?? 5 * 1024 * 1024 * 1024);
