import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SUBTITLE_SESSION_STORAGE_KEY } from '../../app/helpers';

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
  mockReburn,
  renderSubtitleEditor,
  resetSubtitleEditorMocks,
  storeMock,
  subtitleClip,
  subtitleTranscript,
} from './subtitleEditor.test-helpers';

async function switchToClipModeAndSelectClip() {
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: /^clip$/i }));
  await user.click(screen.getByRole('button', { name: /select clip/i }));
  await user.click(screen.getByRole('option', { name: /clip_1\.mp4/i }));
  await waitFor(() => expect(mockGetClipTranscript).toHaveBeenCalledWith('clip_1.mp4', 'proj_1'));
  return user;
}

beforeEach(() => {
  authRuntimeState.canUseProtectedRequests = true;
  resetSubtitleEditorMocks();
});

describe('SubtitleEditor clip mode - core clip sessions', () => {
  it('starts a reburn job for the selected clip', async () => {
    await renderSubtitleEditor();
    const user = await switchToClipModeAndSelectClip();

    await user.click(screen.getByRole('button', { name: /save \+ reburn/i }));

    await waitFor(() => {
      expect(mockReburn).toHaveBeenCalledWith({
        animation_type: 'default',
        clip_name: 'clip_1.mp4',
        project_id: 'proj_1',
        style_name: 'HORMOZI',
        transcript: subtitleTranscript,
      });
    });
  });

  it('persists and resumes the active clip job after a refresh', async () => {
    const view = await renderSubtitleEditor();
    const user = await switchToClipModeAndSelectClip();
    const { SubtitleEditor } = await import('../../components/SubtitleEditor');

    await user.click(screen.getByRole('button', { name: /save \+ reburn/i }));

    await waitFor(() => {
      expect(JSON.parse(window.localStorage.getItem(SUBTITLE_SESSION_STORAGE_KEY) ?? '{}')).toEqual(
        expect.objectContaining({
          clipName: 'clip_1.mp4',
          currentJobId: 'reburn_1',
          jobKind: 'reburn',
          mode: 'clip',
          projectId: 'proj_1',
          selectionKey: 'clip:proj_1:clip_1.mp4',
        }),
      );
    });

    storeMock.jobs = [{
      created_at: 1,
      job_id: 'reburn_1',
      last_message: 'Altyazı yeniden basım başladı...',
      progress: 42,
      project_id: 'proj_1',
      status: 'processing',
      style: 'HORMOZI',
      timeline: [
        {
          at: '2026-03-22T10:00:00.000Z',
          id: 'reburn_1:queued',
          job_id: 'reburn_1',
          message: 'Altyazı yeniden basım kuyruğa alındı...',
          progress: 0,
          source: 'api',
          status: 'queued',
        },
        {
          at: '2026-03-22T10:00:02.000Z',
          id: 'reburn_1:processing',
          job_id: 'reburn_1',
          message: 'Altyazı yeniden basım başladı...',
          progress: 42,
          source: 'worker',
          status: 'processing',
        },
      ],
      url: 'clip_1.mp4',
    }];

    view.rerender(<SubtitleEditor lockedToClip targetClip={subtitleClip} />);

    const statusCard = await screen.findByTestId('subtitle-processing-status');
    expect(statusCard).toBeInTheDocument();
    expect(within(statusCard).getByText(/^reburn$/i)).toBeInTheDocument();
    expect(within(statusCard).getAllByText(/altyazı yeniden basım başladı/i).length).toBeGreaterThan(0);
    expect(within(statusCard).getAllByText(/42%/i).length).toBeGreaterThan(0);
  });

  it('sends edited transcript words with the reburn payload', async () => {
    mockGetClipTranscript.mockResolvedValue({
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
      transcript: [
        {
          end: 4,
          start: 0,
          text: 'First line',
          words: [
            { word: 'First', start: 0, end: 1.5, score: 0.8 },
            { word: 'line', start: 1.5, end: 4, score: 0.9 },
          ],
        },
      ],
      transcript_status: 'ready',
    });

    await renderSubtitleEditor();
    const user = await switchToClipModeAndSelectClip();
    const textarea = await screen.findByDisplayValue('First line');
    await user.clear(textarea);
    await user.type(textarea, 'Fresh copy');
    await user.click(screen.getByRole('button', { name: /save \+ reburn/i }));

    await waitFor(() => {
      expect(mockReburn).toHaveBeenCalledWith({
        animation_type: 'default',
        clip_name: 'clip_1.mp4',
        project_id: 'proj_1',
        style_name: 'HORMOZI',
        transcript: [
          {
            end: 4,
            start: 0,
            text: 'Fresh copy',
            words: [
              { word: 'Fresh', start: 0, end: 2, score: 1 },
              { word: 'copy', start: 2, end: 4, score: 1 },
            ],
          },
        ],
      });
    });
  });

  it('keeps clip transcript controls visible while a completed reburn triggers background reload', async () => {
    const view = await renderSubtitleEditor();
    const user = await switchToClipModeAndSelectClip();
    const { SubtitleEditor } = await import('../../components/SubtitleEditor');

    await user.click(screen.getByRole('button', { name: /save \+ reburn/i }));

    mockGetClipTranscript.mockImplementationOnce(async () => {
      await new Promise<void>((resolve) => window.setTimeout(resolve, 25));
      return {
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
        transcript: subtitleTranscript,
        transcript_status: 'ready',
      };
    });
    storeMock.jobs = [{
      created_at: 1,
      job_id: 'reburn_1',
      last_message: 'Altyazı yeniden basım tamamlandı.',
      progress: 100,
      project_id: 'proj_1',
      status: 'completed',
      style: 'HORMOZI',
      url: 'clip_1.mp4',
    }];

    await act(async () => {
      view.rerender(<SubtitleEditor />);
    });

    expect(await screen.findByText(/subtitle \(2 \/ 2 segment\)/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save \+ reburn/i })).toBeInTheDocument();
    expect(screen.queryByText(/^loading\.\.\.$/i)).not.toBeInTheDocument();
  });

  it('retries a trusted ready clip before surfacing any missing transcript state', async () => {
    mockGetClipTranscript
      .mockRejectedValueOnce(new Error('Temporary backend drift'))
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
        transcript: subtitleTranscript,
        transcript_status: 'ready',
      });

    await renderSubtitleEditor({
      lockedToClip: true,
      targetClip: {
        ...subtitleClip,
        transcript_status: 'ready',
      },
    });

    await waitFor(() => expect(mockGetClipTranscript).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/subtitle \(2 \/ 2 segment\)/i)).toBeInTheDocument();
    expect(screen.queryByText(/clip transcript not found/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/transcript could not be verified/i)).not.toBeInTheDocument();
  });

  it('shows a render quality summary for clip-focused sessions', async () => {
    mockGetClipTranscript.mockResolvedValue({
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
      render_metadata: {
        audio_validation: { audio_validation_status: 'ok', has_audio: true },
        debug_timing: { merged_output_drift_ms: 12.4 },
        render_quality_score: 88,
        tracking_quality: { status: 'good' },
        transcript_quality: { status: 'good' },
      },
      transcript: subtitleTranscript,
      transcript_status: 'ready',
    });

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    const summary = await screen.findByTestId('render-quality-summary');
    expect(summary).toBeInTheDocument();
    expect(screen.getByText(/score 88 \/ 100/i)).toBeInTheDocument();
    expect(screen.getByText(/quality summary/i)).toBeInTheDocument();
    expect(within(summary).getByText(/^tracking$/i)).toBeInTheDocument();
  });

  it('shows the full clip transcript instead of silently filtering to the first 60 seconds', async () => {
    mockGetClipTranscript.mockResolvedValue({
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
      transcript: [
        { end: 10, start: 0, text: 'Intro', words: [] },
        { end: 75, start: 65, text: 'Late segment', words: [] },
      ],
      transcript_status: 'ready',
    });

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    expect(await screen.findByText(/subtitle \(2 \/ 2 segment\)/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue('Late segment')).toBeInTheDocument();
  });
});

describe('SubtitleEditor clip mode - render metadata warnings', () => {
  it('limits render quality warnings to the top three clip issues', async () => {
    mockGetClipTranscript.mockResolvedValue({
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
      render_metadata: {
        audio_validation: { audio_validation_status: 'missing', has_audio: false },
        debug_timing: { merged_output_drift_ms: 120 },
        render_quality_score: 61,
        subtitle_layout_quality: { subtitle_overflow_detected: true },
        tracking_quality: { status: 'fallback' },
        transcript_quality: { status: 'partial' },
      },
      transcript: subtitleTranscript,
      transcript_status: 'ready',
    });

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    expect(await screen.findByText(/tracking fallback was active/i)).toBeInTheDocument();
    expect(screen.getByText(/transcript quality is not complete/i)).toBeInTheDocument();
    expect(screen.getByText(/subtitle overflow detected/i)).toBeInTheDocument();
    expect(screen.queryByText(/a\/v drift increased/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/audio is muted or invalid/i)).not.toBeInTheDocument();
  });
});

describe('SubtitleEditor clip mode - additional render warnings', () => {
  it('surfaces duration, overlap and opening-layout warnings from clip metadata', async () => {
    mockGetClipTranscript.mockResolvedValue({
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
      duration_validation_status: 'too_short',
      last_error: null,
      recommended_strategy: null,
      render_metadata: {
        duration_validation_status: 'too_short',
        layout_validation_status: 'opening_subject_delayed',
        render_quality_score: 62,
        subtitle_layout_quality: {
          simultaneous_event_overlap_count: 2,
          lower_third_collision_detected: true,
        },
        tracking_quality: { status: 'good' },
        transcript_quality: { status: 'good' },
      },
      transcript: subtitleTranscript,
      transcript_status: 'ready',
    });

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    expect(await screen.findByText(/subtitle event overlap detected/i)).toBeInTheDocument();
    expect(screen.getByText(/render duration is outside the requested range/i)).toBeInTheDocument();
    expect(screen.getByText(/speaker entered the frame late/i)).toBeInTheDocument();
    expect(screen.queryByText(/lower-third graphics were detected/i)).not.toBeInTheDocument();
  });

  it('surfaces split jitter warnings from clip metadata', async () => {
    mockGetClipTranscript.mockResolvedValue({
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
      render_metadata: {
        render_quality_score: 58,
        tracking_quality: {
          status: 'degraded',
          panel_swap_count: 1,
          primary_p95_center_jump_px: 13.6,
          startup_settle_ms: 320,
          predict_fallback_active: true,
        },
        transcript_quality: { status: 'good' },
      },
      transcript: subtitleTranscript,
      transcript_status: 'ready',
    });

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    expect(await screen.findByText(/split panel jitter is high/i)).toBeInTheDocument();
    expect(screen.getByText(/opening frame stabilized late/i)).toBeInTheDocument();
    expect(screen.getByText(/stable mode was used because of tracker fallback/i)).toBeInTheDocument();
  });
});

describe.skip('SubtitleEditor clip mode - recovery triggers', () => {
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
      last_message: 'Transkripsiyon başladı...',
      progress: 30,
      status: 'processing',
      style: 'UPLOAD',
      url: '',
    }];

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    expect(await screen.findByText(/waiting for project transcript/i)).toBeInTheDocument();
    expect(screen.getByText(/transkripsiyon başladı/i)).toBeInTheDocument();
    expect(mockRecoverClipTranscript).not.toHaveBeenCalled();
  });
});

describe.skip('SubtitleEditor clip mode - recovery follow-up', () => {
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

    view.rerender(<SubtitleEditor lockedToClip targetClip={subtitleClip} />);

    expect(await screen.findByText(/onceki deneme basarisiz oldu/i)).toBeInTheDocument();
    expect(screen.getByText(/clip transcript not found/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /transcribe from raw video/i }));

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
        transcript: subtitleTranscript,
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

describe('SubtitleEditor clip mode - recovery completion', () => {
  it('refetches the clip transcript after a recovery job completes', async () => {
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

    const view = await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });
    const { SubtitleEditor } = await import('../../components/SubtitleEditor');

    await waitFor(() => expect(mockGetClipTranscript).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockRecoverClipTranscript).toHaveBeenCalledTimes(1));

    mockGetClipTranscript.mockResolvedValue({
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
      transcript: subtitleTranscript,
      transcript_status: 'ready',
    });
    storeMock.jobs = [{
      created_at: 1,
      job_id: 'cliprecover_1',
      last_message: 'done',
      progress: 100,
      status: 'completed',
      style: 'HORMOZI',
      url: '',
    }];

    view.rerender(<SubtitleEditor lockedToClip targetClip={subtitleClip} />);

    await waitFor(() => expect(mockGetClipTranscript).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/clip transcript loaded/i)).toBeInTheDocument();
  });
});

describe('SubtitleEditor clip mode - reburn safeguards', () => {
  it('warns before reburn when no raw backup exists', async () => {
    const confirmMock = vi.spyOn(window, 'confirm');
    mockGetClipTranscript.mockResolvedValue({
      active_job_id: null,
      capabilities: {
        can_recover_from_project: false,
        can_transcribe_source: true,
        has_clip_metadata: true,
        has_clip_transcript: true,
        has_raw_backup: false,
        project_has_transcript: false,
        resolved_project_id: 'proj_1',
      },
      last_error: null,
      recommended_strategy: null,
      transcript: subtitleTranscript,
      transcript_status: 'ready',
    });

    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });
    const user = userEvent.setup();

    expect(await screen.findByText(/reburn warning/i)).toBeInTheDocument();
    confirmMock.mockReturnValueOnce(false);
    await user.click(screen.getByRole('button', { name: /save \+ reburn/i }));
    expect(mockReburn).not.toHaveBeenCalled();

    confirmMock.mockReturnValueOnce(true);
    await user.click(screen.getByRole('button', { name: /save \+ reburn/i }));
    await waitFor(() => expect(mockReburn).toHaveBeenCalledTimes(1));
    confirmMock.mockRestore();
  });
});
