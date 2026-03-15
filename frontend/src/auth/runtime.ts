import { create } from 'zustand';

import type { AppErrorCode } from '../api/errors';
import { getCachedToken, isTokenUsable, resolveTokenExpiration } from './session';

export type BackendAuthStatus = 'fresh' | 'paused' | 'refreshing';

export interface AuthRuntimeState {
  backendAuthStatus: BackendAuthStatus;
  canUseProtectedRequests: boolean;
  pauseReason: AppErrorCode | null;
  tokenExpiresAt: number | null;
}

interface AuthRuntimeActions {
  pauseProtectedRequests: (reason: AppErrorCode, tokenExpiresAt?: number | null) => void;
  resetProtectedRequests: () => void;
  setProtectedRequestsFresh: (token: string | null) => void;
  setProtectedRequestsRefreshing: (tokenExpiresAt?: number | null) => void;
}

type AuthRuntimeStore = AuthRuntimeState & AuthRuntimeActions;

function buildInitialState(): AuthRuntimeState {
  const cachedToken = getCachedToken();
  const tokenExpiresAt = resolveTokenExpiration(cachedToken);

  return {
    backendAuthStatus: cachedToken ? 'fresh' : 'paused',
    canUseProtectedRequests: Boolean(cachedToken),
    pauseReason: null,
    tokenExpiresAt,
  };
}

export const useAuthRuntimeStore = create<AuthRuntimeStore>((set) => ({
  ...buildInitialState(),
  pauseProtectedRequests: (reason, tokenExpiresAt) =>
    set((state) => ({
      backendAuthStatus: 'paused',
      canUseProtectedRequests: false,
      pauseReason: reason,
      tokenExpiresAt: tokenExpiresAt ?? state.tokenExpiresAt,
    })),
  resetProtectedRequests: () => set(buildInitialState()),
  setProtectedRequestsFresh: (token) => {
    const tokenExpiresAt = resolveTokenExpiration(token);
    const canUseProtectedRequests = isTokenUsable(token, tokenExpiresAt);

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
