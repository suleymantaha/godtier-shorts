import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

describe('SubtitleEditor clip mode - recovery follow-up', () => {
  it('keeps manual recovery actions visible after a failed attempt', async () => {
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
      last_error: 'Onceki deneme basarisiz oldu',
      recommended_strategy: 'transcribe_source',
      transcript: [],
      transcript_status: 'failed',
    });

    const view = await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });
    const user = userEvent.setup();
    const { SubtitleEditor } = await import('../../components/SubtitleEditor');

    await waitFor(() => {
      expect(mockRecoverClipTranscript).toHaveBeenCalledWith({
        clip_name: 'clip_1.mp4',
        project_id: 'proj_1',
        strategy: 'auto',
      });
    });

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
      last_error: 'Onceki deneme basarisiz oldu',
      recommended_strategy: 'transcribe_source',
      transcript: [],
      transcript_status: 'failed',
    });
    storeMock.jobs = [{
      created_at: 1,
      error: 'Onceki deneme basarisiz oldu',
      job_id: 'cliprecover_1',
      last_message: 'HATA: Onceki deneme basarisiz oldu',
      progress: 0,
      status: 'error',
      style: 'TRANSCRIPT_RECOVERY',
      url: '',
    }];

  await act(async () => {
    view.rerender(<SubtitleEditor lockedToClip targetClip={subtitleClip} />);
  });

  const retryButton = await screen.findByRole('button', { name: /transcribe from raw video/i });
  expect(screen.getByText(/clip transcript not found/i)).toBeInTheDocument();
  await user.click(retryButton);

    await waitFor(() => {
      expect(mockRecoverClipTranscript).toHaveBeenLastCalledWith({
        clip_name: 'clip_1.mp4',
        project_id: 'proj_1',
        strategy: 'transcribe_source',
      });
    });
  });

  it('shows a mismatch card instead of recovery when a trusted ready clip cannot be verified', async () => {
    mockGetClipTranscript
      .mockResolvedValueOnce({
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
        last_error: 'metadata drift',
        recommended_strategy: 'project_slice',
        transcript: [],
        transcript_status: 'failed',
      })
      .mockResolvedValueOnce({
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
        last_error: 'metadata drift',
        recommended_strategy: 'project_slice',
        transcript: [],
        transcript_status: 'failed',
      })
      .mockResolvedValueOnce({
        active_job_id: null,
        capabilities: {
          can_recover_from_project: true,
          can_transcribe_source: true,
          has_clip_metadata: true,
          has_clip_transcript: true,
          has_raw_backup: true,
          project_has_transcript: true,
          resolved_project_id: 'proj_1',
        },
        last_error: null,
        recommended_strategy: null,
        transcript: [{
          end: 4,
          start: 0,
          text: 'First line',
          words: [],
        }, {
          end: 9,
          start: 5,
          text: 'Second line',
          words: [],
        }],
        transcript_status: 'ready',
      });

    await renderSubtitleEditor({
      lockedToClip: true,
      targetClip: {
        ...subtitleClip,
        transcript_status: 'ready',
      },
    });
    const user = userEvent.setup();

    await waitFor(() => expect(mockGetClipTranscript).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/transcript could not be verified/i)).toBeInTheDocument();
    expect(screen.queryByText(/clip transcript not found/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /verify transcript again/i }));

    await waitFor(() => expect(mockGetClipTranscript).toHaveBeenCalledTimes(3));
    expect(await screen.findByText(/subtitle \(2 \/ 2 segment\)/i)).toBeInTheDocument();
  });
});
