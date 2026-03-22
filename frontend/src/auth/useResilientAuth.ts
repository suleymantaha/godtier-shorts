import { useAuth } from '@clerk/clerk-react';
import { useEffect, useMemo, useState } from 'react';

import { authApi, getFreshToken, setApiToken } from '../api/client';
import { isAppError, type AppError } from '../api/errors';
import { useAuthRuntimeStore } from './runtime';
import {
  AUTH_BOOTSTRAP_TIMEOUT_MS,
} from '../config';
import {
  buildAuthSnapshot,
  clearAuthSnapshot,
  writeAuthSnapshot,
} from './session';
import {
  useBootstrapTimeout,
  useOnlineStatus,
  classifyTokenRefreshError,
  resolveResilientAuthState,
} from './useResilientAuth.helpers';

type NoticeTone = 'danger' | 'info' | 'warning';
const BACKEND_IDENTITY_RETRY_MS = 2000;
const BACKEND_IDENTITY_RETRYABLE_CODES = new Set([
  'auth_provider_unavailable',
  'auth_revalidation_required',
  'token_expired',
  'unauthorized',
]);

export interface AuthNotice {
  message: string;
  title: string;
  tone: NoticeTone;
}

export type ResilientAuthStatus =
  | 'authenticated'
  | 'degraded_authenticated'
  | 'error'
  | 'loading'
  | 'offline_authenticated'
  | 'signed_out';

export interface ResilientAuthState {
  backendAuthStatus: 'fresh' | 'paused' | 'refreshing';
  canAccessApp: boolean;
  canUseBackend: boolean;
  error: AppError | null;
  identityKey: string | null;
  isOnline: boolean;
  notice: AuthNotice | null;
  pauseReason: AppError['code'] | null;
  showUserMenu: boolean;
  status: ResilientAuthStatus;
  tokenExpiresAt: number | null;
}

interface UseBackendIdentitySyncOptions {
  isLoaded: boolean;
  isOnline: boolean;
  resetProtectedRequests: () => void;
  sessionId: string | null;
  signedOut: boolean;
  userId: string | null;
}

export function useResilientAuth(): ResilientAuthState {
  const { isLoaded, isSignedIn, sessionId, userId } = useAuth();
  const isOnline = useOnlineStatus();
  const signedOut = isLoaded && !isSignedIn;
  const bootstrapTimedOut = useBootstrapTimeout(isLoaded, AUTH_BOOTSTRAP_TIMEOUT_MS);
  const backendAuthStatus = useAuthRuntimeStore((state) => state.backendAuthStatus);
  const canUseProtectedRequests = useAuthRuntimeStore((state) => state.canUseProtectedRequests);
  const pauseReason = useAuthRuntimeStore((state) => state.pauseReason);
  const resetProtectedRequests = useAuthRuntimeStore((state) => state.resetProtectedRequests);
  const tokenExpiresAt = useAuthRuntimeStore((state) => state.tokenExpiresAt);
  const { authError, backendIdentity } = useBackendIdentitySync({
    isLoaded,
    isOnline,
    resetProtectedRequests,
    sessionId: sessionId ?? null,
    signedOut,
    userId: userId ?? null,
  });

  const effectiveAuthError = signedOut ? null : authError;
  const effectiveBackendIdentity = signedOut ? null : backendIdentity;

  return useMemo(
    () => ({
      ...resolveResilientAuthState({
        authError: effectiveAuthError,
        backendRuntime: {
          backendAuthStatus,
          canUseProtectedRequests,
          pauseReason,
          tokenExpiresAt,
        },
        bootstrapTimedOut,
        isLoaded,
        isOnline,
        isSignedIn,
      }),
      identityKey: isSignedIn ? effectiveBackendIdentity?.subject ?? userId ?? null : null,
    }),
    [
      backendAuthStatus,
      bootstrapTimedOut,
      canUseProtectedRequests,
      effectiveAuthError,
      effectiveBackendIdentity?.subject,
      isLoaded,
      isOnline,
      isSignedIn,
      pauseReason,
      tokenExpiresAt,
      userId,
    ],
  );
}

function useBackendIdentitySync({
  isLoaded,
  isOnline,
  resetProtectedRequests,
  sessionId,
  signedOut,
  userId,
}: UseBackendIdentitySyncOptions): {
  authError: AppError | null;
  backendIdentity: { subject: string } | null;
} {
  const [authError, setAuthError] = useState<AppError | null>(null);
  const [backendIdentity, setBackendIdentity] = useState<{ subject: string } | null>(null);
  const clearBackendIdentity = useAuthRuntimeStore((state) => state.clearBackendIdentity);
  const setBackendIdentityInStore = useAuthRuntimeStore((state) => state.setBackendIdentity);

  useEffect(() => {
    if (!isLoaded) {
      return;
    }

    if (signedOut) {
      setApiToken(null);
      if (isOnline) {
        clearAuthSnapshot();
      }
      clearBackendIdentity();
      resetProtectedRequests();
      return;
    }

    let cancelled = false;
    let retryTimer: number | null = null;

    const clearRetryTimer = () => {
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer);
        retryTimer = null;
      }
    };

    const attemptSync = async () => {
      const syncSucceeded = await syncBackendIdentity({
        isOnline,
        onError: setAuthError,
        onIdentity: setBackendIdentity,
        onIdentityDetails: setBackendIdentityInStore,
        sessionId,
        userId,
        wasCancelled: () => cancelled,
      });

      if (cancelled || syncSucceeded || !isOnline) {
        return;
      }

      const currentError = useAuthRuntimeStore.getState().pauseReason;
      const shouldRetry = currentError === null || BACKEND_IDENTITY_RETRYABLE_CODES.has(currentError);
      if (!shouldRetry) {
        return;
      }

      clearRetryTimer();
      retryTimer = window.setTimeout(() => {
        retryTimer = null;
        if (!cancelled) {
          void attemptSync();
        }
      }, BACKEND_IDENTITY_RETRY_MS);
    };

    void attemptSync();

    return () => {
      cancelled = true;
      clearRetryTimer();
    };
  }, [clearBackendIdentity, isLoaded, isOnline, resetProtectedRequests, sessionId, setBackendIdentityInStore, signedOut, userId]);

  return { authError, backendIdentity };
}

async function syncBackendIdentity({
  isOnline,
  onError,
  onIdentity,
  onIdentityDetails,
  sessionId,
  userId,
  wasCancelled,
}: {
  isOnline: boolean;
  onError: (error: AppError | null) => void;
  onIdentity: (identity: { subject: string } | null) => void;
  onIdentityDetails: (identity: {
    authMode: 'clerk_jwt' | 'static_token';
    subject: string;
    subjectHash: string;
    tokenType: 'jwt' | 'bearer';
  }) => void;
  sessionId: string | null;
  userId: string | null;
  wasCancelled: () => boolean;
}): Promise<boolean> {
  try {
    const token = await getFreshToken();
    const whoami = await authApi.whoami();
    if (wasCancelled()) {
      return false;
    }

    writeAuthSnapshot(buildAuthSnapshot({
      isSignedIn: true,
      sessionId,
      token,
      userId,
    }));
    onIdentityDetails({
      authMode: whoami.auth_mode,
      subject: whoami.subject,
      subjectHash: whoami.subject_hash,
      tokenType: whoami.token_type,
    });
    onIdentity({ subject: whoami.subject });
    onError(null);
    return true;
  } catch (error) {
    if (wasCancelled()) {
      return false;
    }

    onIdentity(null);
    onError(isAppError(error) ? error : classifyTokenRefreshError(error, isOnline));
    return false;
  }
}
