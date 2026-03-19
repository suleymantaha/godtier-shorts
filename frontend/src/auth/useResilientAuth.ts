import { useAuth } from '@clerk/clerk-react';
import { useEffect, useMemo, useState } from 'react';

import type { AppError } from '../api/errors';
import { authApi, getFreshToken, setApiToken } from '../api/client';
import { isAppError } from '../api/errors';
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

export function useResilientAuth(): ResilientAuthState {
  const { isLoaded, isSignedIn, sessionId, userId } = useAuth();
  const isOnline = useOnlineStatus();
  const bootstrapTimedOut = useBootstrapTimeout(isLoaded, AUTH_BOOTSTRAP_TIMEOUT_MS);
  const [authError, setAuthError] = useState<AppError | null>(null);
  const [backendIdentity, setBackendIdentity] = useState<{ subject: string } | null>(null);
  const backendAuthStatus = useAuthRuntimeStore((state) => state.backendAuthStatus);
  const canUseProtectedRequests = useAuthRuntimeStore((state) => state.canUseProtectedRequests);
  const pauseReason = useAuthRuntimeStore((state) => state.pauseReason);
  const resetProtectedRequests = useAuthRuntimeStore((state) => state.resetProtectedRequests);
  const tokenExpiresAt = useAuthRuntimeStore((state) => state.tokenExpiresAt);

  useEffect(() => {
    if (!isLoaded) {
      return;
    }

    if (!isSignedIn) {
      setApiToken(null);
      setBackendIdentity(null);
      setAuthError(null);
      if (isOnline) {
        clearAuthSnapshot();
      }
      resetProtectedRequests();
      return;
    }

    let cancelled = false;

    const syncToken = async () => {
      try {
        const token = await getFreshToken();
        const whoami = await authApi.whoami();
        if (cancelled) {
          return;
        }

        const nextSnapshot = buildAuthSnapshot({
          isSignedIn: true,
          sessionId,
          token,
          userId,
        });
        writeAuthSnapshot(nextSnapshot);
        setBackendIdentity({ subject: whoami.subject });
        setAuthError(null);
      } catch (error) {
        if (cancelled) {
          return;
        }

        setBackendIdentity(null);
        setAuthError(isAppError(error) ? error : classifyTokenRefreshError(error, isOnline));
      }
    };

    void syncToken();

    return () => {
      cancelled = true;
    };
  }, [isLoaded, isOnline, isSignedIn, resetProtectedRequests, sessionId, userId]);

  return useMemo(
    () => ({
      ...resolveResilientAuthState({
        authError,
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
      identityKey: isSignedIn ? backendIdentity?.subject ?? userId ?? null : null,
    }),
    [
      authError,
      backendAuthStatus,
      backendIdentity?.subject,
      bootstrapTimedOut,
      canUseProtectedRequests,
      isLoaded,
      isOnline,
      isSignedIn,
      pauseReason,
      tokenExpiresAt,
      userId,
    ],
  );
}
