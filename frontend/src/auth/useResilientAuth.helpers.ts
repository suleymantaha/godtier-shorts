import { isClerkRuntimeError } from '@clerk/clerk-react/errors';
import { useEffect, useState } from 'react';

import { createAppError, type AppError, type AppErrorCode } from '../api/errors';
import i18n, { formatTime, normalizeLocale, tSafe } from '../i18n';
import {
  getCachedToken,
  hasOfflineShellAccess,
  readAuthSnapshot,
} from './session';
import type { AuthRuntimeState } from './runtime';
import type { AuthNotice, ResilientAuthState, ResilientAuthStatus } from './useResilientAuth';

interface ResolveResilientAuthStateOptions {
  authError: AppError | null;
  backendRuntime: Pick<AuthRuntimeState, 'backendAuthStatus' | 'canUseProtectedRequests' | 'pauseReason' | 'tokenExpiresAt'>;
  bootstrapTimedOut: boolean;
  isLoaded: boolean;
  isOnline: boolean;
  isSignedIn: boolean | undefined;
}

export function classifyTokenRefreshError(error: unknown, isOnline: boolean): AppError {
  if (!isOnline) {
    return createAppError(
      'network_offline',
      tSafe('auth.errors.networkOffline'),
      { retryable: false, source: 'auth' },
    );
  }

  return isClerkRuntimeError(error)
    ? createAppError(
        'auth_provider_unavailable',
        tSafe('auth.errors.providerUnavailable'),
        { cause: error, retryable: false, source: 'auth' },
      )
    : createAppError(
        'auth_provider_unavailable',
        tSafe('auth.errors.sessionUnavailable'),
        { cause: error, retryable: false, source: 'auth' },
      );
}

function readOnlineStatus(): boolean {
  if (typeof navigator === 'undefined') {
    return true;
  }

  return navigator.onLine;
}

export function useOnlineStatus(): boolean {
  const [isOnline, setIsOnline] = useState(readOnlineStatus);

  useEffect(() => {
    const onOnline = () => setIsOnline(true);
    const onOffline = () => setIsOnline(false);

    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);

    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
    };
  }, []);

  return isOnline;
}

export function useBootstrapTimeout(isLoaded: boolean, timeoutMs: number): boolean {
  const [bootstrapTimedOut, setBootstrapTimedOut] = useState(false);

  useEffect(() => {
    if (isLoaded) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setBootstrapTimedOut(true);
    }, timeoutMs);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [isLoaded, timeoutMs]);

  return bootstrapTimedOut;
}

function formatExpiryLabel(expiresAt: number | null): string {
  if (!expiresAt) {
    return tSafe('auth.time.soon');
  }

  return formatTime(expiresAt, normalizeLocale(i18n.language));
}

function buildOfflineNotice(
  status: ResilientAuthStatus,
  canUseBackend: boolean,
  expiresAt: number | null,
): AuthNotice {
  if (canUseBackend) {
    return {
      message: status === 'offline_authenticated'
        ? tSafe('auth.notices.offlineAuthenticatedBackend', { time: formatExpiryLabel(expiresAt) })
        : tSafe('auth.notices.degradedAuthenticatedBackend', { time: formatExpiryLabel(expiresAt) }),
      title: status === 'offline_authenticated' ? tSafe('auth.notices.offlineMode') : tSafe('auth.notices.authFallbackActive'),
      tone: 'warning',
    };
  }

  return {
    message: status === 'offline_authenticated'
      ? tSafe('auth.notices.offlineAuthenticatedShell')
      : tSafe('auth.notices.degradedAuthenticatedShell'),
    title: status === 'offline_authenticated' ? tSafe('auth.notices.limitedOfflineAccess') : tSafe('auth.notices.limitedAuthAccess'),
    tone: 'info',
  };
}

function buildProtectedAccessNotice(
  pauseReason: AppErrorCode | null,
  canUseBackend: boolean,
  expiresAt: number | null,
): AuthNotice | null {
  if (!pauseReason) {
    return null;
  }

  if (pauseReason === 'network_offline') {
    return {
      message: canUseBackend
        ? tSafe('auth.notices.protectedOfflineWithToken', { time: formatExpiryLabel(expiresAt) })
        : tSafe('auth.notices.protectedOffline'),
      title: canUseBackend ? tSafe('auth.notices.offlineMode') : tSafe('auth.notices.limitedOfflineAccess'),
      tone: 'warning',
    };
  }

  if (pauseReason === 'auth_provider_unavailable') {
    return {
      message: tSafe('auth.notices.providerUnavailable'),
      title: tSafe('auth.notices.authFallbackActive'),
      tone: 'warning',
    };
  }

  if (pauseReason === 'token_expired') {
    return {
      message: tSafe('auth.notices.tokenExpired'),
      title: tSafe('auth.notices.refreshRequired'),
      tone: 'warning',
    };
  }

  if (pauseReason === 'unauthorized') {
    return {
      message: tSafe('auth.notices.unauthorized'),
      title: tSafe('auth.notices.backendSessionUnavailable'),
      tone: 'danger',
    };
  }

  if (pauseReason === 'forbidden') {
    return {
      message: tSafe('auth.notices.forbidden'),
      title: tSafe('auth.notices.accessPermissionRequired'),
      tone: 'danger',
    };
  }

  return null;
}

function buildStaticAuthState(
  status: ResilientAuthStatus,
  overrides: Partial<ResilientAuthState> = {},
): ResilientAuthState {
  return {
    backendAuthStatus: 'paused',
    canAccessApp: false,
    canUseBackend: false,
    error: null,
    identityKey: null,
    isOnline: true,
    notice: null,
    pauseReason: null,
    showUserMenu: false,
    status,
    tokenExpiresAt: null,
    ...overrides,
  };
}

function resolveFallbackAuthState(
  backendRuntime: Pick<AuthRuntimeState, 'backendAuthStatus' | 'canUseProtectedRequests' | 'pauseReason' | 'tokenExpiresAt'>,
  canUseOfflineShell: boolean,
  canUseBackend: boolean,
  isOnline: boolean,
  bootstrapTimedOut: boolean,
  authError: AppError | null,
): ResilientAuthState | null {
  if (!shouldUseFallbackAuthState(isOnline, bootstrapTimedOut, authError, canUseOfflineShell)) {
    return null;
  }

  const snapshot = readAuthSnapshot();
  const tokenExpiresAt = backendRuntime.tokenExpiresAt ?? snapshot?.tokenExpiresAt ?? null;
  const status: ResilientAuthStatus = !isOnline ? 'offline_authenticated' : 'degraded_authenticated';
  const notice = buildProtectedAccessNotice(
    backendRuntime.pauseReason,
    canUseBackend,
    tokenExpiresAt,
  ) ?? buildOfflineNotice(status, canUseBackend, tokenExpiresAt);

  return buildStaticAuthState(status, {
    backendAuthStatus: backendRuntime.backendAuthStatus,
    canAccessApp: true,
    canUseBackend,
    isOnline,
    notice,
    pauseReason: backendRuntime.pauseReason,
    tokenExpiresAt,
  });
}

function shouldUseFallbackAuthState(
  isOnline: boolean,
  bootstrapTimedOut: boolean,
  authError: AppError | null,
  canUseOfflineShell: boolean,
): boolean {
  return canUseOfflineShell && (!isOnline || bootstrapTimedOut || authError !== null);
}

function resolveTerminalAuthState(
  authError: AppError | null,
  backendRuntime: Pick<AuthRuntimeState, 'backendAuthStatus' | 'canUseProtectedRequests' | 'pauseReason' | 'tokenExpiresAt'>,
  bootstrapTimedOut: boolean,
  isLoaded: boolean,
  isOnline: boolean,
  isSignedIn: boolean | undefined,
): ResilientAuthState {
  if (isLoaded && !isSignedIn) {
    return buildStaticAuthState('signed_out', {
      backendAuthStatus: backendRuntime.backendAuthStatus,
      isOnline,
      pauseReason: backendRuntime.pauseReason,
      tokenExpiresAt: backendRuntime.tokenExpiresAt,
    });
  }

  if (authError) {
    return buildStaticAuthState('error', {
      backendAuthStatus: backendRuntime.backendAuthStatus,
      error: authError,
      isOnline,
      notice: buildProtectedAccessNotice(
        backendRuntime.pauseReason,
        backendRuntime.canUseProtectedRequests,
        backendRuntime.tokenExpiresAt,
      ),
      pauseReason: backendRuntime.pauseReason,
      tokenExpiresAt: backendRuntime.tokenExpiresAt,
    });
  }

  return buildStaticAuthState('loading', {
    backendAuthStatus: backendRuntime.backendAuthStatus,
    isOnline,
    notice: bootstrapTimedOut
      ? {
          message: 'Clerk baslatma kontrolu uzadi. Internet baglantinizi ve Clerk erisiminizi kontrol edin.',
          title: 'Kimlik dogrulama basliyor',
          tone: 'warning',
        }
      : buildProtectedAccessNotice(
        backendRuntime.pauseReason,
        backendRuntime.canUseProtectedRequests,
        backendRuntime.tokenExpiresAt,
      ),
    pauseReason: backendRuntime.pauseReason,
    tokenExpiresAt: backendRuntime.tokenExpiresAt,
  });
}

export function resolveResilientAuthState({
  authError,
  backendRuntime,
  bootstrapTimedOut,
  isLoaded,
  isOnline,
  isSignedIn,
}: ResolveResilientAuthStateOptions): ResilientAuthState {
  const cachedToken = getCachedToken();
  const canUseOfflineShell = hasOfflineShellAccess();
  const canUseBackend = backendRuntime.canUseProtectedRequests || Boolean(cachedToken);

  if (isLoaded && isSignedIn) {
    return buildStaticAuthState('authenticated', {
      backendAuthStatus: backendRuntime.backendAuthStatus,
      canAccessApp: true,
      canUseBackend,
      isOnline,
      notice: buildProtectedAccessNotice(
        backendRuntime.pauseReason,
        canUseBackend,
        backendRuntime.tokenExpiresAt,
      ),
      pauseReason: backendRuntime.pauseReason,
      showUserMenu: true,
      tokenExpiresAt: backendRuntime.tokenExpiresAt,
    });
  }

  const fallbackState = resolveFallbackAuthState(
    backendRuntime,
    canUseOfflineShell,
    canUseBackend,
    isOnline,
    bootstrapTimedOut,
    authError,
  );
  if (fallbackState) {
    return fallbackState;
  }

  return resolveTerminalAuthState(authError, backendRuntime, bootstrapTimedOut, isLoaded, isOnline, isSignedIn);
}
