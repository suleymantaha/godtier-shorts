import { getAnimationSelectOptions, getStyleLabel, STYLE_OPTIONS } from '../../config/subtitleStyles';
import { tSafe } from '../../i18n';
import { API_BASE } from '../../config';
import type { Clip, ClipTranscriptCapabilities, ProjectSummary, Segment } from '../../types';
import { syncSegmentTextAndWords } from '../../utils/transcript';
import { getClipUrl } from '../../utils/url';

export type SubtitleEditorMode = 'project' | 'clip';

export type SubtitleProject = ProjectSummary;

export interface VisibleTranscriptEntry {
  index: number;
  segment: Segment;
}

export const EMPTY_CLIP_TRANSCRIPT_CAPABILITIES: ClipTranscriptCapabilities = {
  can_recover_from_project: false,
  can_transcribe_source: false,
  has_clip_metadata: false,
  has_clip_transcript: false,
  has_raw_backup: false,
  project_has_transcript: false,
  resolved_project_id: null,
};

export function getSubtitleStyleOptions() {
  return STYLE_OPTIONS.map((style) => ({ label: getStyleLabel(style), value: style }));
}

export function getSubtitleAnimationOptions() {
  return getAnimationSelectOptions();
}

export function filterSubtitleProjects(projects: SubtitleProject[]): SubtitleProject[] {
  return projects.filter((project) => project.has_master);
}

export function hasSubtitleSelection(
  mode: SubtitleEditorMode,
  selectedProjectId: string | null,
  selectedClip: Clip | null,
): boolean {
  return (mode === 'project' && Boolean(selectedProjectId)) || (mode === 'clip' && Boolean(selectedClip));
}

export function resolveSubtitleSelectionKey(
  mode: SubtitleEditorMode,
  selectedProjectId: string | null,
  selectedClip: Clip | null,
): string | null {
  if (mode === 'project' && selectedProjectId) {
    return `project:${selectedProjectId}`;
  }

  if (mode === 'clip' && selectedClip) {
    const projectId = selectedClip.resolved_project_id ?? selectedClip.project ?? 'legacy';
    return `clip:${projectId}:${selectedClip.name}`;
  }

  return null;
}

export function resolveSubtitleVideoSrc({
  cacheBust,
  mode,
  selectedClip,
  selectedProjectId,
}: {
  cacheBust: number;
  mode: SubtitleEditorMode;
  selectedClip: Clip | null;
  selectedProjectId: string | null;
}): string | undefined {
  if (mode === 'project' && selectedProjectId) {
    return `${API_BASE}/api/projects/${selectedProjectId}/master`;
  }

  if (mode === 'clip' && selectedClip) {
    const clipCacheKey = cacheBust > 0
      ? `${selectedClip.created_at}:${cacheBust}`
      : selectedClip.created_at;
    return getClipUrl(selectedClip, { cacheBust: clipCacheKey });
  }

  return undefined;
}

export function replaceTranscriptText(transcript: Segment[], index: number, text: string): Segment[] {
  return transcript.map((segment, segmentIndex) => (
    segmentIndex === index ? syncSegmentTextAndWords(segment, text) : segment
  ));
}

export function filterVisibleTranscriptEntries(
  transcript: Segment[],
  startTime: number,
  endTime: number,
): VisibleTranscriptEntry[] {
  return transcript.reduce<VisibleTranscriptEntry[]>((entries, segment, index) => {
    if (segment.end > startTime && segment.start < endTime) {
      entries.push({ index, segment });
    }

    return entries;
  }, []);
}

export function resolveTranscriptDuration(transcript: Segment[]): number {
  return transcript.length > 0 ? Math.max(...transcript.map((segment) => segment.end), 60) : 60;
}

export function resolveLoadedEndTime(duration: number, previousEndTime: number): number {
  return previousEndTime > duration || previousEndTime === 60 ? Math.min(60, duration) : previousEndTime;
}

export function resolveCompletionSuccessMessage(mode: SubtitleEditorMode): string {
  return mode === 'clip'
    ? tSafe('subtitleEditor.transcript.transcriptSaved', { defaultValue: 'Transcript saved.' })
    : tSafe('subtitleEditor.transcript.clipRendered', { defaultValue: 'Clip rendered.' });
}

export function resolveClipSelectValue(clip: Clip | null): string {
  return clip ? `${clip.project ?? 'legacy'}:${clip.name}` : '';
}

export function selectClipByValue(clips: Clip[], value: string): Clip | null {
  if (!value) {
    return null;
  }

  const [project, name] = value.split(':');
  return clips.find((clip) => (clip.project ?? 'legacy') === project && clip.name === name) ?? null;
}

function mergeLockedClipContext(matchingClip: Clip, targetClip: Clip): Clip {
  return {
    ...matchingClip,
    has_transcript: matchingClip.has_transcript || targetClip.has_transcript,
    project: matchingClip.project ?? targetClip.project,
    resolved_project_id: matchingClip.resolved_project_id ?? targetClip.resolved_project_id ?? null,
    transcript_status: matchingClip.transcript_status ?? targetClip.transcript_status,
    ui_title: matchingClip.ui_title ?? targetClip.ui_title,
  };
}

function hasSameLockedClipContext(left: Clip, right: Clip): boolean {
  return left.name === right.name
    && left.url === right.url
    && left.has_transcript === right.has_transcript
    && (left.project ?? null) === (right.project ?? null)
    && (left.resolved_project_id ?? null) === (right.resolved_project_id ?? null)
    && (left.transcript_status ?? null) === (right.transcript_status ?? null)
    && (left.ui_title ?? null) === (right.ui_title ?? null);
}

export function reconcileLockedClip(clips: Clip[], targetClip: Clip | null): Clip | null {
  if (!targetClip) {
    return null;
  }

  const targetProjectId = targetClip.resolved_project_id ?? targetClip.project ?? null;
  const matchingByIdentity = clips.find((clip) => {
    if (clip.name !== targetClip.name) {
      return false;
    }

    const clipProjectId = clip.resolved_project_id ?? clip.project ?? null;
    return clipProjectId === targetProjectId;
  });
  if (matchingByIdentity) {
    const mergedClip = mergeLockedClipContext(matchingByIdentity, targetClip);
    return hasSameLockedClipContext(mergedClip, targetClip) ? targetClip : mergedClip;
  }

  const clipsWithSameName = clips.filter((clip) => clip.name === targetClip.name);
  if (clipsWithSameName.length === 1) {
    const mergedClip = mergeLockedClipContext(clipsWithSameName[0], targetClip);
    return hasSameLockedClipContext(mergedClip, targetClip) ? targetClip : mergedClip;
  }

  return targetClip;
}
