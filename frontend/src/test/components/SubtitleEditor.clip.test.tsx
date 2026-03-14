import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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
    resetSubtitleEditorMocks();
  });

  it('starts a reburn job for the selected clip', async () => {
    await renderSubtitleEditor();
    const user = await switchToClipModeAndSelectClip();

    await user.click(screen.getByRole('button', { name: /kaydet \+ reburn/i }));

    await waitFor(() => {
      expect(mockReburn).toHaveBeenCalledWith({
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
