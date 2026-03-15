import { ANIMATION_SELECT_OPTIONS, STYLE_OPTIONS } from '../../config/subtitleStyles';
import { API_BASE } from '../../config';
import type { Clip, ClipTranscriptCapabilities, ProjectSummary, Segment } from '../../types';
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

export const SUBTITLE_STYLE_OPTIONS = STYLE_OPTIONS
  .map((style) => ({ label: style, value: style }));

export const SUBTITLE_ANIMATION_OPTIONS = ANIMATION_SELECT_OPTIONS;

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
    return getClipUrl(selectedClip, { cacheBust: cacheBust || undefined });
  }

  return undefined;
}

export function replaceTranscriptText(transcript: Segment[], index: number, text: string): Segment[] {
  return transcript.map((segment, segmentIndex) => (
    segmentIndex === index ? { ...segment, text } : segment
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
  return mode === 'clip' ? 'Video render edildi. Altyazılar güncellendi.' : 'Klip üretildi.';
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
