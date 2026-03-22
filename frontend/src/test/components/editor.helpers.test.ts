import { describe, expect, it } from 'vitest';

import type { Clip, Segment } from '../../types';
import {
  buildEditorSessionKey,
  filterTranscriptForManualRender,
  formatUploadLimit,
  getTimeRangeError,
  getVisibleTranscriptEntries,
  resolveEditorVideoSrc,
  resolveStoredEditorState,
} from '../../components/editor/helpers';

const clip: Clip = {
  created_at: Date.now(),
  has_transcript: true,
  name: 'clip_1.mp4',
  project: 'proj_1',
  url: '/api/projects/proj_1/files/clip/clip_1.mp4',
};

const transcript: Segment[] = [
  { end: 4, start: 0, text: 'intro', words: [] },
  { end: 8, start: 5, text: 'middle', words: [] },
  { end: 12, start: 9, text: 'outro', words: [] },
];

describe('editor helpers', () => {
  it('formats upload limits in gigabytes', () => {
    expect(formatUploadLimit(1024 * 1024 * 1024)).toBe('1GB');
    expect(formatUploadLimit(3.5 * 1024 * 1024 * 1024)).toBe('3.5GB');
  });

  it('builds session keys for master and clip modes', () => {
    expect(buildEditorSessionKey('master')).toBe('godtier-editor-master-session');
    expect(buildEditorSessionKey('clip', clip)).toBe('godtier-editor-clip-session:proj_1:clip_1.mp4');
  });

  it('resolves clip session values from stored state', () => {
    expect(resolveStoredEditorState('clip', clip, 'proj_1', {
      animationType: 'fade',
      centerX: 0.7,
      currentJobId: 'job_1',
      endTime: 45,
      numClips: 5,
      projectId: 'proj_2',
      startTime: 10,
      style: 'TIKTOK',
      transcript,
    })).toEqual(expect.objectContaining({
      animationType: 'fade',
      centerX: 0.7,
      currentJobId: 'job_1',
      endTime: 45,
      numClips: 5,
      projectId: 'proj_2',
      startTime: 10,
      style: 'TIKTOK',
      transcript,
      clearPersistedSession: false,
    }));
  });

  it('resets master session to defaults', () => {
    expect(resolveStoredEditorState('master', undefined, undefined, {
      currentJobId: 'job_1',
      endTime: 45,
      style: 'TIKTOK',
    })).toEqual(expect.objectContaining({
      animationType: 'default',
      centerX: 0.5,
      currentJobId: null,
      endTime: 60,
      numClips: 3,
      projectId: undefined,
      startTime: 0,
      style: 'HORMOZI',
      transcript: [],
      clearPersistedSession: true,
    }));
  });

  it('derives visible transcript entries and manual transcript ranges', () => {
    expect(getVisibleTranscriptEntries(transcript, 4, 10)).toEqual([
      { index: 1, segment: transcript[1] },
    ]);
    expect(filterTranscriptForManualRender(transcript, 4, 10)).toEqual([transcript[1]]);
  });

  it('validates time ranges and resolves editor video sources', () => {
    expect(getTimeRangeError(10, 5)).toBe('End time must be greater than start time.');
    expect(resolveEditorVideoSrc('blob:preview', 'master', undefined, undefined)).toBe('blob:preview');
    expect(resolveEditorVideoSrc(null, 'clip', clip, undefined)).toContain(`clip_1.mp4?t=${clip.created_at}`);
    expect(resolveEditorVideoSrc(null, 'master', undefined, 'proj_1')).toContain('/api/projects/proj_1/master');
  });
});
