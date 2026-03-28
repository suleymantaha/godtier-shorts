import { describe, expect, it } from 'vitest';

import { AUTH_IDENTITY_STORAGE_KEY } from '../../auth/isolation';
import type { Clip } from '../../types';
import {
  clearSocialConnectStatusQuery,
  clearSocialOAuthStatusQuery,
  getShareComposerIdentityScope,
  buildHashtagsFromInput,
  clearManagedConnectPending,
  buildPublishTargets,
  getPublishSuccessMessage,
  hasManagedConnectPending,
  localDraftKey,
  managedConnectPendingKey,
  markManagedConnectPending,
  mergeDraftContent,
  nowPlusHourLocal,
  parseLocalDraftBuffer,
  readSocialConnectStatusFromQuery,
  readSocialOAuthStatusFromQuery,
  resolveProjectId,
  summarizePublishErrors,
  toggleSelection,
} from '../../components/shareComposer/helpers';
import { createPrefillResponse } from './shareComposer.test-helpers';

describe('shareComposer helpers', () => {
  it('builds deterministic storage keys and local timestamps', () => {
    expect(getShareComposerIdentityScope()).toBe('anonymous');
    expect(localDraftKey('proj_1', 'clip_1.mp4')).toBe('social-share-buffer:anonymous:proj_1:clip_1.mp4');
    expect(managedConnectPendingKey()).toBe('social-postiz-managed-connect-pending:anonymous');
    localStorage.setItem(AUTH_IDENTITY_STORAGE_KEY, 'user-123');
    expect(getShareComposerIdentityScope()).toBe('user-123');
    expect(localDraftKey('proj_1', 'clip_1.mp4')).toBe('social-share-buffer:user-123:proj_1:clip_1.mp4');
    expect(managedConnectPendingKey()).toBe('social-postiz-managed-connect-pending:user-123');
    expect(nowPlusHourLocal(new Date(2026, 2, 14, 8, 5).getTime())).toBe('2026-03-14T09:05');
  });

  it('tracks managed connection pending state per identity scope', () => {
    expect(hasManagedConnectPending()).toBe(false);
    markManagedConnectPending();
    expect(hasManagedConnectPending()).toBe(true);
    clearManagedConnectPending();
    expect(hasManagedConnectPending()).toBe(false);
  });

  it('reads and clears social oauth callback query signal', () => {
    expect(readSocialOAuthStatusFromQuery('?social_oauth=success')).toBe('success');
    expect(readSocialOAuthStatusFromQuery('?social_oauth=error')).toBe('error');
    expect(readSocialOAuthStatusFromQuery('?social_oauth=unknown')).toBeNull();
    expect(readSocialConnectStatusFromQuery('?social_connect=success')).toBe('success');
    expect(readSocialConnectStatusFromQuery('?social_connect=pending')).toBe('pending');
    expect(readSocialConnectStatusFromQuery('?social_connect=unknown')).toBeNull();

    window.history.replaceState({}, '', '/editor?social_oauth=success&foo=1#modal');
    clearSocialOAuthStatusQuery();
    expect(window.location.pathname).toBe('/editor');
    expect(window.location.search).toBe('?foo=1');
    expect(window.location.hash).toBe('#modal');

    window.history.replaceState({}, '', '/social?social_connect=success&session_id=sess_1&platform=youtube_shorts');
    clearSocialConnectStatusQuery();
    expect(window.location.pathname).toBe('/social');
    expect(window.location.search).toBe('');
  });

  it('parses and merges local draft buffers onto server content', () => {
    const parsed = parseLocalDraftBuffer(JSON.stringify({
      youtube_shorts: { hashtags: ['custom'], text: 'LOCAL', title: 'LOCAL TITLE' },
    }));

    expect(parsed.invalid).toBe(false);
    expect(mergeDraftContent(createPrefillResponse().platforms, parsed.buffer).youtube_shorts).toEqual({
      cta_text: 'Follow for the next part.',
      hashtags: ['custom'],
      hook_text: 'HOOK',
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

    expect(getPublishSuccessMessage('now', false)).toBe('Share jobs were added to the queue.');
    expect(getPublishSuccessMessage('scheduled', false)).toBe('The video was added to the Postiz calendar.');
    expect(getPublishSuccessMessage('scheduled', true)).toBe('The scheduled post was added to the approval queue.');
    expect(summarizePublishErrors([{ error: 'quota' }, { error: 'token' }])).toBe('quota | token');
    expect(resolveProjectId(clip)).toBe('proj_1');
    expect(resolveProjectId({ ...clip, project: 'legacy' })).toBeNull();
  });
});
