import { beforeEach, describe, expect, it } from 'vitest';

import {
  AUTH_SNAPSHOT_STORAGE_KEY,
  buildAuthSnapshot,
  getCachedToken,
  hasOfflineShellAccess,
  resolveTokenExpiration,
  writeAuthSnapshot,
} from '../../auth/session';

function createToken(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expSecondsFromNow }));

  return `${header}.${payload}.signature`;
}

describe('auth session helpers', () => {
  beforeEach(() => {
    localStorage.removeItem(AUTH_SNAPSHOT_STORAGE_KEY);
  });

  it('extracts token expiration from a JWT payload', () => {
    const token = createToken(300);
    const expiresAt = resolveTokenExpiration(token);

    expect(expiresAt).not.toBeNull();
    expect(expiresAt).toBeGreaterThan(Date.now());
  });

  it('returns cached token when a stored snapshot still has a valid token', () => {
    const token = createToken(300);
    writeAuthSnapshot(buildAuthSnapshot({
      isSignedIn: true,
      sessionId: 'sess_123',
      token,
      userId: 'user_123',
    }));

    expect(getCachedToken()).toBeTypeOf('string');
    expect(hasOfflineShellAccess()).toBe(true);
  });
});
