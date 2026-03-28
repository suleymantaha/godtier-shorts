import { beforeEach, describe, expect, it } from 'vitest';

import { buildAuthSnapshot, resolveTokenExpiration, writeAuthSnapshot } from '../../auth/session';
import { useAuthRuntimeStore } from '../../auth/runtime';

function createToken(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expSecondsFromNow }));

  return `${header}.${payload}.signature`;
}

describe('auth runtime fallback access', () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthRuntimeStore.setState({
      backendAuthStatus: 'paused',
      canUseProtectedRequests: false,
      pauseReason: null,
      tokenExpiresAt: null,
    });
  });

  it('keeps protected requests usable for retryable auth fallback reasons while the cached token is still valid', () => {
    const token = createToken(300);
    writeAuthSnapshot(buildAuthSnapshot({
      isSignedIn: true,
      sessionId: 'sess_123',
      token,
      userId: 'user_123',
    }));

    useAuthRuntimeStore.getState().resetProtectedRequests();
    useAuthRuntimeStore.getState().pauseProtectedRequests('auth_provider_unavailable', resolveTokenExpiration(token));

    expect(useAuthRuntimeStore.getState()).toMatchObject({
      backendAuthStatus: 'paused',
      canUseProtectedRequests: true,
      pauseReason: 'auth_provider_unavailable',
    });
  });

  it('still blocks protected requests when the token is expired or unauthorized', () => {
    const token = createToken(300);
    writeAuthSnapshot(buildAuthSnapshot({
      isSignedIn: true,
      sessionId: 'sess_123',
      token,
      userId: 'user_123',
    }));

    useAuthRuntimeStore.getState().resetProtectedRequests();
    useAuthRuntimeStore.getState().pauseProtectedRequests('token_expired', resolveTokenExpiration(token));

    expect(useAuthRuntimeStore.getState()).toMatchObject({
      backendAuthStatus: 'paused',
      canUseProtectedRequests: false,
      pauseReason: 'token_expired',
    });
  });

  it('marks protected requests fresh while a short-lived token is still active', () => {
    const token = createToken(30);

    useAuthRuntimeStore.getState().setProtectedRequestsFresh(token);

    expect(useAuthRuntimeStore.getState()).toMatchObject({
      backendAuthStatus: 'fresh',
      canUseProtectedRequests: true,
      pauseReason: null,
    });
  });
});
