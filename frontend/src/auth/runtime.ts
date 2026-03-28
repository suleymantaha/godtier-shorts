import { create } from 'zustand';

import type { AppErrorCode } from '../api/errors';
import { getCachedToken, isTokenActive, resolveTokenExpiration } from './session';

export type BackendAuthStatus = 'fresh' | 'paused' | 'refreshing';

export interface BackendIdentity {
  authMode: 'clerk_jwt' | 'static_token';
  subject: string;
  subjectHash: string;
  tokenType: 'jwt' | 'bearer';
}

export interface AuthRuntimeState {
  backendAuthStatus: BackendAuthStatus;
  backendIdentity: BackendIdentity | null;
  canUseProtectedRequests: boolean;
  pauseReason: AppErrorCode | null;
  tokenExpiresAt: number | null;
}

interface AuthRuntimeActions {
  clearBackendIdentity: () => void;
  pauseProtectedRequests: (reason: AppErrorCode, tokenExpiresAt?: number | null) => void;
  resetProtectedRequests: () => void;
  setBackendIdentity: (identity: BackendIdentity) => void;
  setProtectedRequestsFresh: (token: string | null) => void;
  setProtectedRequestsRefreshing: (tokenExpiresAt?: number | null) => void;
}

type AuthRuntimeStore = AuthRuntimeState & AuthRuntimeActions;

function canUseProtectedFallback(reason: AppErrorCode, tokenExpiresAt: number | null): boolean {
  if (reason === 'forbidden' || reason === 'token_expired' || reason === 'unauthorized') {
    return false;
  }

  const cachedToken = getCachedToken();
  const cachedTokenExpiresAt = resolveTokenExpiration(cachedToken);
  const effectiveTokenExpiresAt = tokenExpiresAt ?? cachedTokenExpiresAt;

  return isTokenActive(cachedToken, effectiveTokenExpiresAt);
}

function buildInitialState(): AuthRuntimeState {
  const cachedToken = getCachedToken();
  const tokenExpiresAt = resolveTokenExpiration(cachedToken);

  return {
    backendAuthStatus: cachedToken ? 'fresh' : 'paused',
    backendIdentity: null,
    canUseProtectedRequests: Boolean(cachedToken),
    pauseReason: null,
    tokenExpiresAt,
  };
}

export const useAuthRuntimeStore = create<AuthRuntimeStore>((set) => ({
  ...buildInitialState(),
  clearBackendIdentity: () => set({ backendIdentity: null }),
  pauseProtectedRequests: (reason, tokenExpiresAt) =>
    set((state) => ({
      backendAuthStatus: 'paused',
      canUseProtectedRequests: canUseProtectedFallback(reason, tokenExpiresAt ?? state.tokenExpiresAt),
      pauseReason: reason,
      tokenExpiresAt: tokenExpiresAt ?? state.tokenExpiresAt,
    })),
  resetProtectedRequests: () => set(buildInitialState()),
  setBackendIdentity: (identity) => set({ backendIdentity: identity }),
  setProtectedRequestsFresh: (token) => {
    const tokenExpiresAt = resolveTokenExpiration(token);
    const canUseProtectedRequests = isTokenActive(token, tokenExpiresAt);

    set({
      backendAuthStatus: canUseProtectedRequests ? 'fresh' : 'paused',
      canUseProtectedRequests,
      pauseReason: null,
      tokenExpiresAt,
    });
  },
  setProtectedRequestsRefreshing: (tokenExpiresAt) =>
    set((state) => ({
      backendAuthStatus: 'refreshing',
      canUseProtectedRequests: false,
      pauseReason: null,
      tokenExpiresAt: tokenExpiresAt ?? state.tokenExpiresAt,
    })),
}));
