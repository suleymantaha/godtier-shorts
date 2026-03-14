import { describe, expect, it } from 'vitest';

import type { Clip } from '../../types';
import {
  buildHashtagsFromInput,
  buildPublishTargets,
  getPublishSuccessMessage,
  localDraftKey,
  mergeDraftContent,
  nowPlusHourLocal,
  parseLocalDraftBuffer,
  resolveProjectId,
  summarizePublishErrors,
  toggleSelection,
} from '../../components/shareComposer/helpers';
import { createPrefillResponse } from './shareComposer.test-helpers';

describe('shareComposer helpers', () => {
  it('builds deterministic storage keys and local timestamps', () => {
    expect(localDraftKey('proj_1', 'clip_1.mp4')).toBe('social-share-buffer:proj_1:clip_1.mp4');
    expect(nowPlusHourLocal(new Date(2026, 2, 14, 8, 5).getTime())).toBe('2026-03-14T09:05');
  });

  it('parses and merges local draft buffers onto server content', () => {
    const parsed = parseLocalDraftBuffer(JSON.stringify({
      youtube_shorts: { hashtags: ['custom'], text: 'LOCAL', title: 'LOCAL TITLE' },
    }));

    expect(parsed.invalid).toBe(false);
    expect(mergeDraftContent(createPrefillResponse().platforms, parsed.buffer).youtube_shorts).toEqual({
      hashtags: ['custom'],
      text: 'LOCAL',
      title: 'LOCAL TITLE',
    });
  });

  it('normalizes hashtags, account selections and publish targets', () => {
    expect(buildHashtagsFromInput(' #viral, growth , ,#focus ')).toEqual(['viral', 'growth', 'focus']);
    expect(toggleSelection(['acc_1'], 'acc_2')).toEqual(['acc_1', 'acc_2']);
    expect(toggleSelection(['acc_1', 'acc_2'], 'acc_1')).toEqual(['acc_2']);
    expect(buildPublishTargets(
      [{ id: 'acc_1', name: 'YT', platform: 'youtube_shorts', provider: 'youtube' }],
      ['acc_1'],
    )).toEqual([{ account_id: 'acc_1', platform: 'youtube_shorts', provider: 'youtube' }]);
  });

  it('summarizes publish outcomes and resolves valid project ids', () => {
    const clip: Clip = {
      created_at: Date.now(),
      has_transcript: true,
      name: 'clip_1.mp4',
      project: 'proj_1',
      url: '/api/projects/proj_1/files/clip/clip_1.mp4',
    };

    expect(getPublishSuccessMessage('now', false)).toBe('Paylaşım jobları kuyruğa alındı.');
    expect(getPublishSuccessMessage('scheduled', false)).toBe('Video Postiz takvimine eklendi.');
    expect(getPublishSuccessMessage('scheduled', true)).toBe('Takvimli paylaşım onay kuyruğuna alındı.');
    expect(summarizePublishErrors([{ error: 'quota' }, { error: 'token' }])).toBe('quota | token');
    expect(resolveProjectId(clip)).toBe('proj_1');
    expect(resolveProjectId({ ...clip, project: 'legacy' })).toBeNull();
  });
});
