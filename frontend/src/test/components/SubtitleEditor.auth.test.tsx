import { act, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authRuntimeState = {
  canUseProtectedRequests: true,
  pauseReason: null as string | null,
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
    vi.useRealTimers();
    authRuntimeState.canUseProtectedRequests = true;
    authRuntimeState.pauseReason = null;
    resetSubtitleEditorMocks();
  });

  it('skips bootstrap requests until protected auth is ready', async () => {
    authRuntimeState.canUseProtectedRequests = false;

    const view = await renderSubtitleEditor();

    expect(storeMock.fetchJobs).not.toHaveBeenCalled();
    expect(mockGetProjects).not.toHaveBeenCalled();
    expect(mockListClips).not.toHaveBeenCalled();
    expect(view.getByText(/preparing project and clip list/i)).toBeInTheDocument();
    expect(view.queryByText(/no projects yet/i)).not.toBeInTheDocument();
  });

  it('skips clip transcript loading while protected auth is paused', async () => {
    authRuntimeState.canUseProtectedRequests = false;
    authRuntimeState.pauseReason = 'unauthorized';

    const view = await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    expect(mockGetClipTranscript).not.toHaveBeenCalled();
    expect(view.getByText(/transcript access pending/i)).toBeInTheDocument();
    expect(view.queryByText(/clip transcript not found/i)).not.toBeInTheDocument();
  });

  it('retries locked clip transcript loading when auth bootstrap stays in loading', async () => {
    vi.useFakeTimers();
    authRuntimeState.canUseProtectedRequests = false;

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    expect(mockGetClipTranscript).not.toHaveBeenCalled();
    expect(screen.getByText(/subtitle \(0 \/ 0 segment\)/i)).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2600);
      await Promise.resolve();
    });

    expect(mockGetClipTranscript).toHaveBeenCalledWith(subtitleClip.name, subtitleClip.project);
    expect(screen.getByDisplayValue('First line')).toBeInTheDocument();
  });
});
