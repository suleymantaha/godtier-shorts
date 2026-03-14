import type { Clip } from '../types';
import { readStored } from '../utils/storage';

export type AppViewMode = 'config' | 'manual' | 'subtitle';

interface StoredAppState {
  viewMode?: string;
  editingClip?: Clip | null;
  subtitleTargetClip?: Clip | null;
}

export interface AppState {
  viewMode: AppViewMode;
  editingClip: Clip | null;
  subtitleTargetClip: Clip | null;
}

export const APP_STATE_STORAGE_KEY = 'godtier-app-state';
export const DEFAULT_APP_STATE: AppState = { viewMode: 'config', editingClip: null, subtitleTargetClip: null };

export function readAppState(): AppState {
  const parsed = readStored<StoredAppState>(APP_STATE_STORAGE_KEY, DEFAULT_APP_STATE);
  return {
    viewMode: normalizeViewMode(parsed.viewMode),
    editingClip: parsed.editingClip ?? null,
    subtitleTargetClip: parsed.subtitleTargetClip ?? null,
  };
}

export function persistAppState(viewMode: AppViewMode, editingClip: Clip | null, subtitleTargetClip: Clip | null) {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(
    APP_STATE_STORAGE_KEY,
    JSON.stringify({ viewMode, editingClip, subtitleTargetClip }),
  );
}

function normalizeViewMode(viewMode?: string): AppViewMode {
  if (viewMode === 'manual' || viewMode === 'subtitle') {
    return viewMode;
  }

  return 'config';
}
