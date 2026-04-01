import { screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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
  mockRecoverClipTranscript,
  renderSubtitleEditor,
  resetSubtitleEditorMocks,
  storeMock,
  subtitleClip,
} from './subtitleEditor.test-helpers';

beforeEach(() => {
  authRuntimeState.canUseProtectedRequests = true;
  resetSubtitleEditorMocks();
});

describe('SubtitleEditor clip mode - recovery triggers', () => {
  it('auto-starts smart transcript recovery when the selected clip transcript is missing', async () => {
    mockGetClipTranscript.mockResolvedValue({
      active_job_id: null,
      capabilities: {
        can_recover_from_project: true,
        can_transcribe_source: true,
        has_clip_metadata: true,
        has_clip_transcript: false,
        has_raw_backup: true,
        project_has_transcript: true,
        resolved_project_id: 'proj_1',
      },
      last_error: null,
      recommended_strategy: 'project_slice',
      transcript: [],
      transcript_status: 'needs_recovery',
    });

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    await waitFor(() => {
      expect(mockRecoverClipTranscript).toHaveBeenCalledWith({
        clip_name: 'clip_1.mp4',
        project_id: 'proj_1',
        strategy: 'auto',
      });
    });
  });

  it('shows waiting state when project transcript is still pending for a clip', async () => {
    mockGetClipTranscript.mockResolvedValue({
      active_job_id: 'upload_1',
      capabilities: {
        can_recover_from_project: false,
        can_transcribe_source: true,
        has_clip_metadata: true,
        has_clip_transcript: false,
        has_raw_backup: false,
        project_has_transcript: false,
        resolved_project_id: 'proj_1',
      },
      last_error: null,
      recommended_strategy: 'project_slice',
      transcript: [],
      transcript_status: 'project_pending',
    });
    storeMock.jobs = [{
      created_at: 1,
      job_id: 'upload_1',
      last_message: 'Transkripsiyon ba\u015Flad\u0131...',
      progress: 30,
      status: 'processing',
      style: 'UPLOAD',
      url: '',
    }];

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    expect(await screen.findByText(/waiting for project transcript/i)).toBeInTheDocument();
    const statusCard = screen.getByTestId('subtitle-processing-status');
    expect(within(statusCard).getAllByText(/transkripsiyon ba\u015Flad\u0131/i).length).toBeGreaterThan(0);
    expect(mockRecoverClipTranscript).not.toHaveBeenCalled();
  });
});
