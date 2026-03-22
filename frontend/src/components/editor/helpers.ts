import { API_BASE } from '../../config';
import { tSafe } from '../../i18n';
import type { Clip, Segment } from '../../types';
import { getClipUrl } from '../../utils/url';
import { isStyleName, isSubtitleAnimationType, type StyleName, type SubtitleAnimationType } from '../../config/subtitleStyles';
import { readStored } from '../../utils/storage';

export const MASTER_EDITOR_SESSION_KEY = 'godtier-editor-master-session';

type EditorStateDefaults = {
  animationType: SubtitleAnimationType;
  centerX: number;
  currentJobId: string | null;
  endTime: number;
  numClips: number;
  startTime: number;
  style: StyleName;
  transcript: Segment[];
};

const DEFAULT_EDITOR_STATE: EditorStateDefaults = {
  animationType: 'default',
  centerX: 0.5,
  currentJobId: null,
  endTime: 60,
  numClips: 3,
  startTime: 0,
  style: 'HORMOZI',
  transcript: [],
};

export interface StoredEditorSession {
  animationType?: SubtitleAnimationType;
  centerX?: number;
  currentJobId?: string | null;
  endTime?: number;
  numClips?: number;
  projectId?: string;
  startTime?: number;
  style?: StyleName;
  transcript?: Segment[];
}

export type ResolvedEditorSessionState = EditorStateDefaults & {
  clearPersistedSession: boolean;
  projectId?: string;
};

export interface VisibleTranscriptEntry {
  index: number;
  segment: Segment;
}

export function formatUploadLimit(bytes: number): string {
  const gb = bytes / (1024 * 1024 * 1024);

  return Number.isInteger(gb) ? `${gb}GB` : `${gb.toFixed(1)}GB`;
}

export function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function buildEditorSessionKey(mode: 'master' | 'clip', targetClip?: Clip): string {
  if (mode === 'clip' && targetClip) {
    return `godtier-editor-clip-session:${targetClip.project ?? 'legacy'}:${targetClip.name}`;
  }

  return MASTER_EDITOR_SESSION_KEY;
}

export function readStoredEditorSession(sessionKey: string): StoredEditorSession | null {
  return readStored<StoredEditorSession | null>(sessionKey, null);
}

export function resolveClipProjectId(targetClip?: Clip): string | undefined {
  return targetClip?.project && targetClip.project !== 'legacy' ? targetClip.project : undefined;
}

export function resolveStoredEditorState(
  mode: 'master' | 'clip',
  targetClip: Clip | undefined,
  clipProjectId: string | undefined,
  stored: StoredEditorSession | null,
): ResolvedEditorSessionState {
  if (mode !== 'clip' || !targetClip) {
    return buildDefaultEditorSessionState();
  }

  return buildClipEditorSessionState(stored, clipProjectId);
}

export function buildStoredEditorSession(state: Omit<ResolvedEditorSessionState, 'clearPersistedSession'>): StoredEditorSession {
  return {
    centerX: state.centerX,
    animationType: state.animationType,
    currentJobId: state.currentJobId,
    endTime: state.endTime,
    numClips: state.numClips,
    projectId: state.projectId,
    startTime: state.startTime,
    style: state.style,
    transcript: state.transcript,
  };
}

export function clampLoadedMetadataEndTime(duration: number): number {
  return Math.min(60, duration);
}

export function getVisibleTranscriptEntries(transcript: Segment[], startTime: number, endTime: number): VisibleTranscriptEntry[] {
  return transcript.reduce<VisibleTranscriptEntry[]>((entries, segment, index) => {
    if (segment.start >= startTime && segment.end <= endTime) {
      entries.push({ index, segment });
    }

    return entries;
  }, []);
}

export function filterTranscriptForManualRender(transcript: Segment[], startTime: number, endTime: number): Segment[] {
  return transcript.filter((segment) => segment.start >= startTime && segment.end <= endTime);
}

export function findTranscriptIndexAtTime(transcript: Segment[], time: number): number {
  return transcript.findIndex((segment) => time >= segment.start && time <= segment.end);
}

export function getTimeRangeError(startTime: number, endTime: number): string | null {
  return endTime <= startTime ? tSafe('editorWorkspace.errors.invalidRange') : null;
}

export function resolveEditorVideoSrc(
  localSrc: string | null,
  mode: 'master' | 'clip',
  targetClip: Clip | undefined,
  projectId: string | undefined,
): string | undefined {
  if (localSrc) {
    return localSrc;
  }

  if (mode === 'clip' && targetClip) {
    return getClipUrl(targetClip, { cacheBust: targetClip.created_at });
  }

  return projectId ? `${API_BASE}/api/projects/${projectId}/master` : undefined;
}

function resolveStoredJobId(value: string | null | undefined): string | null {
  return typeof value === 'string' ? value : DEFAULT_EDITOR_STATE.currentJobId;
}

function resolveStoredNumber(value: number | undefined, fallback: number): number {
  return typeof value === 'number' ? value : fallback;
}

function resolveStoredStyle(value: unknown): StyleName {
  return isStyleName(value) ? value : DEFAULT_EDITOR_STATE.style;
}

function resolveStoredAnimationType(value: unknown): SubtitleAnimationType {
  return isSubtitleAnimationType(value) ? value : DEFAULT_EDITOR_STATE.animationType;
}

function resolveStoredTranscript(value: Segment[] | undefined): Segment[] {
  return Array.isArray(value) ? value : DEFAULT_EDITOR_STATE.transcript;
}

function buildDefaultEditorSessionState(): ResolvedEditorSessionState {
  return {
    ...DEFAULT_EDITOR_STATE,
    clearPersistedSession: true,
    projectId: undefined,
  };
}

function buildClipEditorSessionState(
  stored: StoredEditorSession | null,
  clipProjectId: string | undefined,
): ResolvedEditorSessionState {
  return {
    centerX: resolveStoredNumber(stored?.centerX, DEFAULT_EDITOR_STATE.centerX),
    animationType: resolveStoredAnimationType(stored?.animationType),
    clearPersistedSession: false,
    currentJobId: resolveStoredJobId(stored?.currentJobId),
    endTime: resolveStoredNumber(stored?.endTime, DEFAULT_EDITOR_STATE.endTime),
    numClips: resolveStoredNumber(stored?.numClips, DEFAULT_EDITOR_STATE.numClips),
    projectId: stored?.projectId ?? clipProjectId,
    startTime: resolveStoredNumber(stored?.startTime, DEFAULT_EDITOR_STATE.startTime),
    style: resolveStoredStyle(stored?.style),
    transcript: resolveStoredTranscript(stored?.transcript),
  };
}
