import { screen, waitFor } from '@testing-library/react';
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

it('opens as a locked single-clip session from the gallery', async () => {
  await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

  await waitFor(() => expect(mockGetClipTranscript).toHaveBeenCalledWith('clip_1.mp4', 'proj_1'));
  expect(screen.queryByRole('button', { name: /^clip$/i })).not.toBeInTheDocument();
  expect(screen.getByText(/focused clip: clip_1\.mp4/i)).toBeInTheDocument();
});
