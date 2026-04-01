import { waitFor } from '@testing-library/react';
import { beforeEach, vi, it, expect } from 'vitest';

const authRuntimeState = {
  canUseProtectedRequests: true,
};

vi.mock('../../auth/runtime', () => ({
  useAuthRuntimeStore: Object.assign(
    (selector: (state: typeof authRuntimeState) => unknown) => selector(authRuntimeState),
    { getState: () => authRuntimeState },
  ),
}));

import {
  mockGetClipTranscript,
  renderSubtitleEditor,
  resetSubtitleEditorMocks,
  subtitleClip,
} from './subtitleEditor.test-helpers';

beforeEach(() => {
  authRuntimeState.canUseProtectedRequests = true;
  resetSubtitleEditorMocks();
});

it('reconciles a stale locked clip payload against the live clip list before loading transcript', async () => {
  await renderSubtitleEditor({
    lockedToClip: true,
    targetClip: {
      ...subtitleClip,
      project: 'legacy',
    },
  });

  await waitFor(() => expect(mockGetClipTranscript).toHaveBeenCalledWith('clip_1.mp4', 'proj_1'));
});
