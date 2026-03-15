import { APP_STATE_STORAGE_KEY } from '../app/helpers';
import { AUTH_SNAPSHOT_STORAGE_KEY } from './session';

export const AUTH_IDENTITY_STORAGE_KEY = 'godtier-auth-identity';

const USER_SCOPED_PREFIXES = [
  'godtier-editor-clip-session:',
  'social-share-buffer:',
];

const USER_SCOPED_KEYS = [
  APP_STATE_STORAGE_KEY,
  AUTH_SNAPSHOT_STORAGE_KEY,
  'godtier-auto-cut-session',
  'godtier-editor-master-session',
];

function hasUserScopedClientState(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  for (const key of USER_SCOPED_KEYS) {
    if (window.localStorage.getItem(key) !== null) {
      return true;
    }
  }

  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (!key) {
      continue;
    }
    if (USER_SCOPED_PREFIXES.some((prefix) => key.startsWith(prefix))) {
      return true;
    }
  }

  return false;
}

export function clearUserScopedClientState(): void {
  if (typeof window === 'undefined') {
    return;
  }

  for (const key of USER_SCOPED_KEYS) {
    window.localStorage.removeItem(key);
  }

  const keysToRemove: string[] = [];
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (!key) {
      continue;
    }
    if (USER_SCOPED_PREFIXES.some((prefix) => key.startsWith(prefix))) {
      keysToRemove.push(key);
    }
  }

  for (const key of keysToRemove) {
    window.localStorage.removeItem(key);
  }
}

export function syncIdentityBoundary(identityKey: string | null): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  const previousIdentity = window.localStorage.getItem(AUTH_IDENTITY_STORAGE_KEY);
  const hasScopedState = hasUserScopedClientState();
  if (!identityKey) {
    if (!previousIdentity) {
      return false;
    }
    clearUserScopedClientState();
    window.localStorage.removeItem(AUTH_IDENTITY_STORAGE_KEY);
    return true;
  }

  if (previousIdentity === identityKey) {
    return false;
  }

  if (previousIdentity !== null || hasScopedState) {
    clearUserScopedClientState();
    window.localStorage.setItem(AUTH_IDENTITY_STORAGE_KEY, identityKey);
    return true;
  }

  window.localStorage.setItem(AUTH_IDENTITY_STORAGE_KEY, identityKey);
  return false;
}
