import { describe, expect, it } from 'vitest';

import type { Clip, Segment } from '../../types';
import {
  filterSubtitleProjects,
  filterVisibleTranscriptEntries,
  hasSubtitleSelection,
  replaceTranscriptText,
  resolveClipSelectValue,
  resolveCompletionSuccessMessage,
  resolveLoadedEndTime,
  resolveSubtitleVideoSrc,
  resolveTranscriptDuration,
  selectClipByValue,
} from '../../components/subtitleEditor/helpers';

const clip: Clip = {
  created_at: Date.now(),
  has_transcript: true,
  name: 'clip_1.mp4',
  project: 'proj_1',
  url: '/api/projects/proj_1/files/clip/clip_1.mp4',
};

const transcript: Segment[] = [
  { end: 4, start: 0, text: 'First line', words: [] },
  { end: 9, start: 5, text: 'Second line', words: [] },
];

describe('subtitleEditor helpers', () => {
  it('filters valid projects and selection states', () => {
    expect(filterSubtitleProjects([
      { active_job_id: null, has_master: true, has_transcript: true, id: 'proj_1', last_error: null, transcript_status: 'ready' },
      { active_job_id: 'upload_1', has_master: true, has_transcript: false, id: 'proj_2', last_error: null, transcript_status: 'pending' },
    ])).toEqual([
      { active_job_id: null, has_master: true, has_transcript: true, id: 'proj_1', last_error: null, transcript_status: 'ready' },
      { active_job_id: 'upload_1', has_master: true, has_transcript: false, id: 'proj_2', last_error: null, transcript_status: 'pending' },
    ]);
    expect(hasSubtitleSelection('project', 'proj_1', null)).toBe(true);
    expect(hasSubtitleSelection('clip', null, clip)).toBe(true);
    expect(hasSubtitleSelection('project', null, null)).toBe(false);
  });

  it('resolves video sources and clip selections', () => {
    expect(resolveSubtitleVideoSrc({
      cacheBust: 0,
      mode: 'project',
      selectedClip: null,
      selectedProjectId: 'proj_1',
    })).toContain('/api/projects/proj_1/master');
    expect(resolveSubtitleVideoSrc({
      cacheBust: 3,
      mode: 'clip',
      selectedClip: clip,
      selectedProjectId: null,
    })).toContain(`clip_1.mp4?t=${clip.created_at}%3A3`);
    expect(resolveSubtitleVideoSrc({
      cacheBust: 0,
      mode: 'clip',
      selectedClip: clip,
      selectedProjectId: null,
    })).toContain(`clip_1.mp4?t=${clip.created_at}`);
    expect(resolveClipSelectValue(clip)).toBe('proj_1:clip_1.mp4');
    expect(selectClipByValue([clip], 'proj_1:clip_1.mp4')).toEqual(clip);
  });

  it('updates transcript state and visible ranges', () => {
    expect(replaceTranscriptText(transcript, 1, 'Updated line')[1].text).toBe('Updated line');
    expect(filterVisibleTranscriptEntries(transcript, 4, 8)).toEqual([
      { index: 1, segment: transcript[1] },
    ]);
    expect(resolveTranscriptDuration(transcript)).toBe(60);
    expect(resolveLoadedEndTime(32, 60)).toBe(32);
  });

  it('preserves existing word timings when edited text keeps the same token count', () => {
    const timedTranscript: Segment[] = [
      {
        end: 4,
        start: 0,
        text: 'First line',
        words: [
          { word: 'First', start: 0, end: 1.5, score: 0.8 },
          { word: 'line', start: 1.5, end: 4, score: 0.9 },
        ],
      },
    ];

    expect(replaceTranscriptText(timedTranscript, 0, 'Fresh copy')[0]).toEqual({
      end: 4,
      start: 0,
      text: 'Fresh copy',
      words: [
        { word: 'Fresh', start: 0, end: 1.5, score: 0.8 },
        { word: 'copy', start: 1.5, end: 4, score: 0.9 },
      ],
    });
  });

  it('rebuilds word timings when edited text changes token count or becomes empty', () => {
    const timedTranscript: Segment[] = [
      {
        end: 4,
        start: 0,
        text: 'First line',
        words: [
          { word: 'First', start: 0, end: 2, score: 0.8 },
          { word: 'line', start: 2, end: 4, score: 0.9 },
        ],
      },
    ];

    expect(replaceTranscriptText(timedTranscript, 0, 'Fresh new copy')[0]).toEqual({
      end: 4,
      start: 0,
      text: 'Fresh new copy',
      words: [
        { word: 'Fresh', start: 0, end: 4 / 3, score: 1 },
        { word: 'new', start: 4 / 3, end: 8 / 3, score: 1 },
        { word: 'copy', start: 8 / 3, end: 4, score: 1 },
      ],
    });
    expect(replaceTranscriptText(timedTranscript, 0, '   ')[0].words).toEqual([]);
  });

  it('derives completion messages', () => {
    expect(resolveCompletionSuccessMessage('project')).toBe('Klip üretildi.');
    expect(resolveCompletionSuccessMessage('clip')).toBe('Video render edildi. Altyazılar güncellendi.');
  });
});
