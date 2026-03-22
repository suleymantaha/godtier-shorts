import type { Clip } from '../types';
import { readStored } from '../utils/storage';

export type AppViewMode = 'config' | 'manual' | 'subtitle' | 'social' | 'social_compose';
export type SubtitleSessionMode = 'project' | 'clip';
export type SubtitleSessionJobKind = 'reburn' | 'clip_recovery' | 'project_transcript' | 'range_render' | 'unknown';

interface StoredAppState {
  viewMode?: string;
  editingClip?: Clip | null;
  subtitleTargetClip?: Clip | null;
}

interface StoredSubtitleSessionSnapshot {
  clipName?: string | null;
  currentJobId?: string | null;
  jobKind?: string;
  mode?: string;
  projectId?: string | null;
  selectionKey?: string;
  startedAt?: number;
}

export interface AppState {
  viewMode: AppViewMode;
  editingClip: Clip | null;
  subtitleTargetClip: Clip | null;
}

export interface SubtitleSessionSnapshot {
  clipName: string | null;
  currentJobId: string | null;
  jobKind: SubtitleSessionJobKind;
  mode: SubtitleSessionMode;
  projectId: string | null;
  selectionKey: string;
  startedAt: number;
}

export const APP_STATE_STORAGE_KEY = 'godtier-app-state';
export const SUBTITLE_SESSION_STORAGE_KEY = 'godtier-subtitle-session';
export const DEFAULT_APP_STATE: AppState = { viewMode: 'config', editingClip: null, subtitleTargetClip: null };

export function normalizeStoredClip(clip?: Clip | null): Clip | null {
  if (!clip) {
    return null;
  }

  return {
    ...clip,
    resolved_project_id: clip.resolved_project_id ?? null,
    transcript_status: clip.transcript_status ?? (clip.has_transcript ? 'ready' : undefined),
  };
}

export function readAppState(): AppState {
  const parsed = readStored<StoredAppState>(APP_STATE_STORAGE_KEY, DEFAULT_APP_STATE);
  const queryMode = readQueryViewMode();
  return {
    viewMode: queryMode ?? normalizeViewMode(parsed.viewMode),
    editingClip: parsed.editingClip ?? null,
    subtitleTargetClip: normalizeStoredClip(parsed.subtitleTargetClip),
  };
}

export function persistAppState(viewMode: AppViewMode, editingClip: Clip | null, subtitleTargetClip: Clip | null) {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(
    APP_STATE_STORAGE_KEY,
    JSON.stringify({ viewMode, editingClip, subtitleTargetClip: normalizeStoredClip(subtitleTargetClip) }),
  );
}

export function readSubtitleSessionSnapshot(): SubtitleSessionSnapshot | null {
  const parsed = readStored<StoredSubtitleSessionSnapshot | null>(SUBTITLE_SESSION_STORAGE_KEY, null);
  if (!parsed || typeof parsed.selectionKey !== 'string' || !parsed.selectionKey) {
    return null;
  }

  return {
    clipName: typeof parsed.clipName === 'string' ? parsed.clipName : null,
    currentJobId: typeof parsed.currentJobId === 'string' ? parsed.currentJobId : null,
    jobKind: normalizeSubtitleSessionJobKind(parsed.jobKind),
    mode: parsed.mode === 'clip' ? 'clip' : 'project',
    projectId: typeof parsed.projectId === 'string' ? parsed.projectId : null,
    selectionKey: parsed.selectionKey,
    startedAt: typeof parsed.startedAt === 'number' && Number.isFinite(parsed.startedAt) ? parsed.startedAt : Date.now(),
  };
}

export function persistSubtitleSessionSnapshot(snapshot: SubtitleSessionSnapshot) {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(SUBTITLE_SESSION_STORAGE_KEY, JSON.stringify(snapshot));
}

export function clearSubtitleSessionSnapshot() {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.removeItem(SUBTITLE_SESSION_STORAGE_KEY);
}

function normalizeViewMode(viewMode?: string): AppViewMode {
  if (viewMode === 'manual' || viewMode === 'subtitle' || viewMode === 'social' || viewMode === 'social_compose') {
    return viewMode;
  }

  return 'config';
}

export function readQueryViewMode(search = typeof window !== 'undefined' ? window.location.search : ''): AppViewMode | null {
  if (!search) {
    return null;
  }
  const params = new URLSearchParams(search);
  return normalizeQueryTab(params.get('tab'));
}

export function syncViewModeToUrl(viewMode: AppViewMode): void {
  if (typeof window === 'undefined') {
    return;
  }
  const currentUrl = new URL(window.location.href);
  const queryTab = queryTabForViewMode(viewMode);
  if (queryTab) {
    currentUrl.searchParams.set('tab', queryTab);
  } else {
    currentUrl.searchParams.delete('tab');
  }
  const nextQuery = currentUrl.searchParams.toString();
  const nextUrl = `${currentUrl.pathname}${nextQuery ? `?${nextQuery}` : ''}${currentUrl.hash}`;
  window.history.replaceState({}, '', nextUrl);
}

function queryTabForViewMode(viewMode: AppViewMode): string | null {
  if (viewMode === 'manual') {
    return 'manual';
  }
  if (viewMode === 'subtitle') {
    return 'subtitle';
  }
  if (viewMode === 'social') {
    return 'social';
  }
  if (viewMode === 'social_compose') {
    return 'social-compose';
  }
  return null;
}

function normalizeQueryTab(tab: string | null): AppViewMode | null {
  if (tab === 'manual') {
    return 'manual';
  }
  if (tab === 'subtitle') {
    return 'subtitle';
  }
  if (tab === 'social') {
    return 'social';
  }
  if (tab === 'social-compose') {
    return 'social_compose';
  }
  return null;
}

function normalizeSubtitleSessionJobKind(jobKind?: string): SubtitleSessionJobKind {
  if (jobKind === 'reburn' || jobKind === 'clip_recovery' || jobKind === 'project_transcript' || jobKind === 'range_render') {
    return jobKind;
  }

  return 'unknown';
}
