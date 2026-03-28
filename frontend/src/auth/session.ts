import {
  AUTH_TOKEN_EXPIRY_SKEW_MS,
  ENABLE_OFFLINE_TOKEN_CACHE,
  OFFLINE_AUTH_SNAPSHOT_TTL_MS,
} from '../config';
import { readStored } from '../utils/storage';

export const AUTH_SNAPSHOT_STORAGE_KEY = 'godtier-auth-snapshot';

export interface AuthSnapshot {
  isSignedIn: boolean;
  sessionId: string | null;
  token: string | null;
  tokenExpiresAt: number | null;
  updatedAt: number;
  userId: string | null;
}

export interface BuildAuthSnapshotOptions {
  isSignedIn: boolean;
  sessionId?: string | null;
  token?: string | null;
  updatedAt?: number;
  userId?: string | null;
}

export function resolveTokenExpiration(token: string | null): number | null {
  if (!token) {
    return null;
  }

  try {
    const [, payload] = token.split('.');
    if (!payload) {
      return null;
    }

    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padding = normalized.length % 4 === 0 ? '' : '='.repeat(4 - (normalized.length % 4));
    const decoded = JSON.parse(atob(`${normalized}${padding}`)) as { exp?: number };

    return typeof decoded.exp === 'number' ? decoded.exp * 1000 : null;
  } catch {
    return null;
  }
}

export function isTokenUsable(token: string | null, tokenExpiresAt: number | null, now = Date.now()): boolean {
  if (!token) {
    return false;
  }

  if (tokenExpiresAt === null) {
    return true;
  }

  return tokenExpiresAt - AUTH_TOKEN_EXPIRY_SKEW_MS > now;
}

export function isTokenActive(token: string | null, tokenExpiresAt: number | null, now = Date.now()): boolean {
  if (!token) {
    return false;
  }

  if (tokenExpiresAt === null) {
    return true;
  }

  return tokenExpiresAt > now;
}

export function buildAuthSnapshot({
  isSignedIn,
  sessionId = null,
  token = null,
  updatedAt = Date.now(),
  userId = null,
}: BuildAuthSnapshotOptions): AuthSnapshot {
  const persistedToken = ENABLE_OFFLINE_TOKEN_CACHE ? token : null;

  return {
    isSignedIn,
    sessionId,
    token: persistedToken,
    tokenExpiresAt: persistedToken ? resolveTokenExpiration(persistedToken) : resolveTokenExpiration(token),
    updatedAt,
    userId,
  };
}

export function readAuthSnapshot(): AuthSnapshot | null {
  const snapshot = readStored<AuthSnapshot | null>(AUTH_SNAPSHOT_STORAGE_KEY, null);

  if (!snapshot || typeof snapshot !== 'object') {
    return null;
  }

  if (typeof snapshot.isSignedIn !== 'boolean' || typeof snapshot.updatedAt !== 'number') {
    return null;
  }

  return {
    isSignedIn: snapshot.isSignedIn,
    sessionId: typeof snapshot.sessionId === 'string' ? snapshot.sessionId : null,
    token: typeof snapshot.token === 'string' ? snapshot.token : null,
    tokenExpiresAt: typeof snapshot.tokenExpiresAt === 'number' ? snapshot.tokenExpiresAt : null,
    updatedAt: snapshot.updatedAt,
    userId: typeof snapshot.userId === 'string' ? snapshot.userId : null,
  };
}

export function writeAuthSnapshot(snapshot: AuthSnapshot | null): void {
  if (typeof window === 'undefined') {
    return;
  }

  if (!snapshot) {
    window.localStorage.removeItem(AUTH_SNAPSHOT_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(AUTH_SNAPSHOT_STORAGE_KEY, JSON.stringify(snapshot));
}

export function clearAuthSnapshot(): void {
  writeAuthSnapshot(null);
}

export function getCachedToken(now = Date.now()): string | null {
  const snapshot = readAuthSnapshot();
  if (!snapshot) {
    return null;
  }

  return isTokenUsable(snapshot.token, snapshot.tokenExpiresAt, now) ? snapshot.token : null;
}

export function hasOfflineShellAccess(now = Date.now()): boolean {
  const snapshot = readAuthSnapshot();
  if (!snapshot?.isSignedIn) {
    return false;
  }

  if (snapshot.token && isTokenUsable(snapshot.token, snapshot.tokenExpiresAt, now)) {
    return true;
  }

  return now - snapshot.updatedAt <= OFFLINE_AUTH_SNAPSHOT_TTL_MS;
}
