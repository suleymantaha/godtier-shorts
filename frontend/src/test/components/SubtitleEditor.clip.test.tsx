import { screen, waitFor } from '@testing-library/react';
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
  mockReburn,
  renderSubtitleEditor,
  resetSubtitleEditorMocks,
  storeMock,
  subtitleClip,
  subtitleTranscript,
} from './subtitleEditor.test-helpers';

async function switchToClipModeAndSelectClip() {
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: /^klip$/i }));
  await user.click(screen.getByRole('button', { name: /klip seçin/i }));
  await user.click(screen.getByRole('option', { name: /clip_1\.mp4/i }));
  await waitFor(() => expect(mockGetClipTranscript).toHaveBeenCalledWith('clip_1.mp4', 'proj_1'));
  return user;
}

describe('SubtitleEditor clip mode', () => {
  beforeEach(() => {
    authRuntimeState.canUseProtectedRequests = true;
    resetSubtitleEditorMocks();
  });

  it('starts a reburn job for the selected clip', async () => {
    await renderSubtitleEditor();
    const user = await switchToClipModeAndSelectClip();

    await user.click(screen.getByRole('button', { name: /kaydet \+ reburn/i }));

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

  it('opens as a locked single-clip session from the gallery', async () => {
    await renderSubtitleEditor({ lockedToClip: true, targetClip: subtitleClip });

    await waitFor(() => expect(mockGetClipTranscript).toHaveBeenCalledWith('clip_1.mp4', 'proj_1'));
    expect(screen.queryByRole('button', { name: /^klip$/i })).not.toBeInTheDocument();
    expect(screen.getByText(/odak klip: clip_1\.mp4/i)).toBeInTheDocument();
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

    expect(await screen.findByTestId('render-quality-summary')).toBeInTheDocument();
    expect(screen.getByText(/score 88 \/ 100/i)).toBeInTheDocument();
    expect(screen.getByText(/kalite özeti/i)).toBeInTheDocument();
    expect(screen.getByText(/tracking/i)).toBeInTheDocument();
  });

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

    expect(await screen.findByText(/tracking fallback aktifti/i)).toBeInTheDocument();
    expect(screen.getByText(/transcript kalitesi tam değil/i)).toBeInTheDocument();
    expect(screen.getByText(/subtitle overflow tespit edildi/i)).toBeInTheDocument();
    expect(screen.queryByText(/a\/v drift yükseldi/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/audio muted veya geçersiz/i)).not.toBeInTheDocument();
  });

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

    expect(await screen.findByText(/subtitle event overlap tespit edildi/i)).toBeInTheDocument();
    expect(screen.getByText(/render süresi istenen aralığın dışında/i)).toBeInTheDocument();
    expect(screen.getByText(/konuşmacı kadraja geç girdi/i)).toBeInTheDocument();
    expect(screen.queryByText(/lower-third grafik algılandı/i)).not.toBeInTheDocument();
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

    expect(await screen.findByText(/split panel jitter yüksek/i)).toBeInTheDocument();
    expect(screen.getByText(/açılış kadrajı geç stabilize oldu/i)).toBeInTheDocument();
    expect(screen.getByText(/tracker fallback nedeniyle stabil mod kullanıldı/i)).toBeInTheDocument();
  });

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

    expect(await screen.findByText(/proje transcripti bekleniyor/i)).toBeInTheDocument();
    expect(screen.getByText(/transkripsiyon başladı/i)).toBeInTheDocument();
    expect(mockRecoverClipTranscript).not.toHaveBeenCalled();
  });

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
    expect(screen.getByText(/klip transkripti bulunamadi/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /ham videodan transkript cikar/i }));

    await waitFor(() => {
      expect(mockRecoverClipTranscript).toHaveBeenLastCalledWith({
        clip_name: 'clip_1.mp4',
        project_id: 'proj_1',
        strategy: 'transcribe_source',
      });
    });
  });

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
    expect(await screen.findByText(/klip transkripti yüklendi/i)).toBeInTheDocument();
  });

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

    expect(await screen.findByText(/reburn uyarisi/i)).toBeInTheDocument();
    confirmMock.mockReturnValueOnce(false);
    await user.click(screen.getByRole('button', { name: /kaydet \+ reburn/i }));
    expect(mockReburn).not.toHaveBeenCalled();

    confirmMock.mockReturnValueOnce(true);
    await user.click(screen.getByRole('button', { name: /kaydet \+ reburn/i }));
    await waitFor(() => expect(mockReburn).toHaveBeenCalledTimes(1));
    confirmMock.mockRestore();
  });
});
