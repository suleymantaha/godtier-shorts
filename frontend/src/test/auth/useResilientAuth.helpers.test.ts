import { beforeEach, describe, expect, it } from 'vitest';

import { createAppError } from '../../api/errors';
import { buildAuthSnapshot, writeAuthSnapshot } from '../../auth/session';
import { resolveResilientAuthState } from '../../auth/useResilientAuth.helpers';

function createToken(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expSecondsFromNow }));

  return `${header}.${payload}.signature`;
}

beforeEach(() => {
  localStorage.clear();
});

describe('useResilientAuth helpers - authenticated states', () => {
  it('returns authenticated state when Clerk is loaded and signed in', () => {
    expect(resolveResilientAuthState({
      authError: null,
      backendRuntime: {
        backendAuthStatus: 'fresh',
        canUseProtectedRequests: true,
        pauseReason: null,
        tokenExpiresAt: null,
      },
      bootstrapTimedOut: false,
      isLoaded: true,
      isOnline: true,
      isSignedIn: true,
    })).toMatchObject({
      canAccessApp: true,
      canUseBackend: true,
      showUserMenu: true,
      status: 'authenticated',
    });
  });

  it('returns offline authenticated state when a valid cached snapshot exists', () => {
    writeAuthSnapshot(buildAuthSnapshot({
      isSignedIn: true,
      sessionId: 'sess_123',
      token: createToken(300),
      userId: 'user_123',
    }));

    expect(resolveResilientAuthState({
      authError: null,
      backendRuntime: {
        backendAuthStatus: 'paused',
        canUseProtectedRequests: false,
        pauseReason: 'network_offline',
        tokenExpiresAt: null,
      },
      bootstrapTimedOut: false,
      isLoaded: false,
      isOnline: false,
      isSignedIn: undefined,
    })).toMatchObject({
      canAccessApp: true,
      canUseBackend: true,
      showUserMenu: false,
      status: 'offline_authenticated',
    });
  });
});

describe('useResilientAuth helpers - fallback handling', () => {
  it('returns error state when there is no usable fallback snapshot', () => {
    expect(resolveResilientAuthState({
      authError: createAppError('auth_provider_unavailable', 'auth down'),
      backendRuntime: {
        backendAuthStatus: 'paused',
        canUseProtectedRequests: false,
        pauseReason: 'auth_provider_unavailable',
        tokenExpiresAt: null,
      },
      bootstrapTimedOut: false,
      isLoaded: false,
      isOnline: true,
      isSignedIn: undefined,
    })).toMatchObject({
      canAccessApp: false,
      canUseBackend: false,
      showUserMenu: false,
      status: 'error',
    });
  });

  it('keeps the shell authenticated while protected requests are paused', () => {
    expect(resolveResilientAuthState({
      authError: null,
      backendRuntime: {
        backendAuthStatus: 'paused',
        canUseProtectedRequests: false,
        pauseReason: 'token_expired',
        tokenExpiresAt: null,
      },
      bootstrapTimedOut: false,
      isLoaded: true,
      isOnline: true,
      isSignedIn: true,
    })).toMatchObject({
      canAccessApp: true,
      canUseBackend: false,
      pauseReason: 'token_expired',
      showUserMenu: true,
      status: 'authenticated',
    });
  });
});
