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

function readNumberEnv(value: string | undefined, fallback: number): number {
  const parsed = Number(value);

  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function readBooleanEnv(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) {
    return fallback;
  }

  return value === '1' || value.toLowerCase() === 'true';
}

export const API_BASE = envUrl ?? 'http://localhost:8000';
export const WS_BASE = API_BASE.replace(/^http/, 'ws');
export const CLERK_PUBLISHABLE_KEY = (import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined) ?? '';
export const CLERK_JWT_TEMPLATE = (import.meta.env.VITE_CLERK_JWT_TEMPLATE as string | undefined) ?? '';

export const MAX_UPLOAD_BYTES = Number((import.meta.env.VITE_MAX_UPLOAD_BYTES as string | undefined) ?? 5 * 1024 * 1024 * 1024);
export const API_REQUEST_TIMEOUT_MS = readNumberEnv(import.meta.env.VITE_API_REQUEST_TIMEOUT_MS as string | undefined, 15000);
export const API_RETRY_COUNT = readNumberEnv(import.meta.env.VITE_API_RETRY_COUNT as string | undefined, 1);
export const AUTH_BOOTSTRAP_TIMEOUT_MS = readNumberEnv(import.meta.env.VITE_AUTH_BOOTSTRAP_TIMEOUT_MS as string | undefined, 6000);
export const AUTH_TOKEN_EXPIRY_SKEW_MS = readNumberEnv(import.meta.env.VITE_AUTH_TOKEN_EXPIRY_SKEW_MS as string | undefined, 60000);
export const OFFLINE_AUTH_SNAPSHOT_TTL_MS = readNumberEnv(import.meta.env.VITE_OFFLINE_AUTH_SNAPSHOT_TTL_MS as string | undefined, 12 * 60 * 60 * 1000);
export const ENABLE_OFFLINE_TOKEN_CACHE = readBooleanEnv(
  import.meta.env.VITE_ENABLE_OFFLINE_TOKEN_CACHE as string | undefined,
  import.meta.env.DEV,
);
