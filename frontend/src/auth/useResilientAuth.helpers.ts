import { isClerkRuntimeError } from '@clerk/clerk-react/errors';
import { useEffect, useState } from 'react';

import { createAppError, type AppError, type AppErrorCode } from '../api/errors';
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
      'Internet baglantisi yok. Onceki oturumla devam etmek icin onbellekte gecerli bir oturum bulunmali.',
      { retryable: false, source: 'auth' },
    );
  }

  return isClerkRuntimeError(error)
    ? createAppError(
        'auth_provider_unavailable',
        'Kimlik dogrulama servisine su anda ulasilamiyor. Lutfen biraz sonra tekrar deneyin.',
        { cause: error, retryable: false, source: 'auth' },
      )
    : createAppError(
        'auth_provider_unavailable',
        'Oturum dogrulanamadi. Lutfen internet baglantinizi kontrol edip tekrar deneyin.',
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
    return 'yakinda';
  }

  return new Date(expiresAt).toLocaleTimeString('tr-TR', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function buildOfflineNotice(
  status: ResilientAuthStatus,
  canUseBackend: boolean,
  expiresAt: number | null,
): AuthNotice {
  if (canUseBackend) {
    return {
      message: status === 'offline_authenticated'
        ? `Onbellekteki oturum kullaniliyor. API erisimi token suresi dolana kadar devam eder: ${formatExpiryLabel(expiresAt)}`
        : `Clerk dogrulamasi gecici olarak cevap vermiyor. Onbellekteki oturum ile devam ediliyor: ${formatExpiryLabel(expiresAt)}`,
      title: status === 'offline_authenticated' ? 'Offline mod' : 'Auth fallback aktif',
      tone: 'warning',
    };
  }

  return {
    message: status === 'offline_authenticated'
      ? 'Kabuk acildi ancak yeni API/WebSocket istekleri icin internet baglantisi geri gelmeli.'
      : 'Kabuk acildi ancak Clerk tekrar dogrulanana kadar korumali istekler bekletilmeli.',
    title: status === 'offline_authenticated' ? 'Sinirli offline erisim' : 'Sinirli auth erisimi',
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
        ? `Internet yok, yeni veriler duraklatildi. Mevcut token ${formatExpiryLabel(expiresAt)} zamanina kadar kullanilabilir.`
        : 'Internet yok, yeni veriler duraklatildi.',
      title: canUseBackend ? 'Offline mod' : 'Sinirli offline erisim',
      tone: 'warning',
    };
  }

  if (pauseReason === 'auth_provider_unavailable') {
    return {
      message: 'Oturum yenilenemiyor, baglanti gelince devam edecek.',
      title: 'Auth fallback aktif',
      tone: 'warning',
    };
  }

  if (pauseReason === 'token_expired') {
    return {
      message: 'Oturum yenilenemedi, korumali islemler beklemeye alindi.',
      title: 'Oturum yenileme gerekli',
      tone: 'warning',
    };
  }

  if (pauseReason === 'unauthorized') {
    return {
      message: 'Backend oturumu dogrulanamadi. Ayni Clerk hesabi ile giris yaptiginizi ve backend auth ayarlarini kontrol edin.',
      title: 'Backend oturumu dogrulanamadi',
      tone: 'danger',
    };
  }

  if (pauseReason === 'forbidden') {
    return {
      message: 'Bu hesapla korumali medya ve proje kaynaklarina erisim izni bulunmuyor.',
      title: 'Erisim izni gerekli',
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
  if ((!isOnline || bootstrapTimedOut || authError) && canUseOfflineShell) {
    const snapshot = readAuthSnapshot();
    const status: ResilientAuthStatus = !isOnline ? 'offline_authenticated' : 'degraded_authenticated';
    const notice = buildProtectedAccessNotice(
      backendRuntime.pauseReason,
      canUseBackend,
      backendRuntime.tokenExpiresAt ?? snapshot?.tokenExpiresAt ?? null,
    ) ?? buildOfflineNotice(status, canUseBackend, snapshot?.tokenExpiresAt ?? null);

    return buildStaticAuthState(status, {
      backendAuthStatus: backendRuntime.backendAuthStatus,
      canAccessApp: true,
      canUseBackend,
      isOnline,
      notice,
      pauseReason: backendRuntime.pauseReason,
      tokenExpiresAt: backendRuntime.tokenExpiresAt ?? snapshot?.tokenExpiresAt ?? null,
    });
  }

  return null;
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
