import { setApiToken } from '../api/client';
import { useAuthRuntimeStore } from './runtime';
import { AUTH_IDENTITY_STORAGE_KEY, clearUserScopedClientState } from './isolation';
import { clearAuthSnapshot } from './session';

export function clearClientAccountState(): void {
  if (typeof window !== 'undefined') {
    clearUserScopedClientState();
    clearAuthSnapshot();
    window.localStorage.removeItem(AUTH_IDENTITY_STORAGE_KEY);
  }

  setApiToken(null);
  useAuthRuntimeStore.getState().resetProtectedRequests();
}

export function hardReloadPage(): void {
  if (typeof window !== 'undefined') {
    window.location.reload();
  }
}
