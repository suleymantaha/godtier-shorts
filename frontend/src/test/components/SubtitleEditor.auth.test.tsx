import { beforeEach, describe, expect, it, vi } from 'vitest';

const authRuntimeState = {
  canUseProtectedRequests: true,
};

vi.mock('../../auth/runtime', () => ({
  useAuthRuntimeStore: (selector: (state: typeof authRuntimeState) => unknown) => selector(authRuntimeState),
}));

import {
  mockGetClipTranscript,
  mockGetProjects,
  mockListClips,
  renderSubtitleEditor,
  resetSubtitleEditorMocks,
  storeMock,
  subtitleClip,
} from './subtitleEditor.test-helpers';

describe('SubtitleEditor auth gating', () => {
  beforeEach(() => {
    authRuntimeState.canUseProtectedRequests = true;
    resetSubtitleEditorMocks();
  });

  it('skips bootstrap requests until protected auth is ready', async () => {
    authRuntimeState.canUseProtectedRequests = false;

    await renderSubtitleEditor();

    expect(storeMock.fetchJobs).not.toHaveBeenCalled();
    expect(mockGetProjects).not.toHaveBeenCalled();
    expect(mockListClips).not.toHaveBeenCalled();
  });

  it('skips clip transcript loading while protected auth is paused', async () => {
    authRuntimeState.canUseProtectedRequests = false;

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    expect(mockGetClipTranscript).not.toHaveBeenCalled();
  });
});
