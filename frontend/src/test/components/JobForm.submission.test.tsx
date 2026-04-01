import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import {
  mockCacheStatus,
  mockFetchJobs,
  mockMergeJobTimelineEvent,
  mockRegisterQueuedJob,
  mockRequestClipsRefresh,
  mockStart,
  renderJobForm,
} from './jobForm.test-helpers';

describe('JobForm submission flow - submit states', () => {
  it('shows error message on failed submit', async () => {
    const user = userEvent.setup();
    await renderJobForm();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /launch pipeline/i }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('disables style select and sends skip_subtitles when subtitles are skipped', async () => {
    mockStart.mockResolvedValueOnce({ status: 'queued', job_id: 'test', message: 'queued', processing_locked: true, gpu_locked: false });
    const user = userEvent.setup();
    await renderJobForm();

    const toggle = screen.getByRole('switch', { name: /skip subtitle processing/i });
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByLabelText(/visual style/i)).toBeDisabled();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /launch pipeline/i }));

    expect(mockStart).toHaveBeenCalledWith(expect.objectContaining({ skip_subtitles: true }));
  });

  it('refreshes jobs and clears the url after successful submit', async () => {
    mockStart.mockResolvedValueOnce({
      status: 'queued',
      job_id: 'test',
      message: 'İşlem başlatılıyor. Hazırlık aşamaları yürütülüyor...',
      processing_locked: false,
      gpu_locked: false,
    });
    const user = userEvent.setup();
    await renderJobForm();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /launch pipeline/i }));

    await waitFor(() => expect(mockFetchJobs).toHaveBeenCalledTimes(1));
    expect(mockRegisterQueuedJob).toHaveBeenCalledWith({
      job_id: 'test',
      message: 'İşlem başlatılıyor. Hazırlık aşamaları yürütülüyor...',
      style: 'TIKTOK',
      url: 'https://youtube.com/watch?v=test123',
    });
    expect(mockMergeJobTimelineEvent).toHaveBeenCalledWith(expect.objectContaining({
      job_id: 'test',
      status: 'processing',
      progress: 1,
    }));
    expect(screen.getByLabelText(/source feed url/i)).toHaveValue('');
  });

  it('reuses an existing job without creating a duplicate optimistic queue entry', async () => {
    mockStart.mockResolvedValueOnce({
      status: 'queued',
      job_id: 'existing-job',
      message: 'Bu ayarlarla zaten aktif bir islem var. Mevcut is takip ediliyor.',
      existing_job: true,
      processing_locked: true,
      gpu_locked: false,
    });
    const user = userEvent.setup();
    await renderJobForm();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /launch pipeline/i }));

    await waitFor(() => expect(mockFetchJobs).toHaveBeenCalledTimes(1));
    expect(mockRegisterQueuedJob).not.toHaveBeenCalled();
    expect(mockMergeJobTimelineEvent).not.toHaveBeenCalled();
    expect(screen.getByText(/zaten aktif bir islem var/i)).toBeInTheDocument();
  });

  it('does not register a queued job when the backend returns cached', async () => {
    mockStart.mockResolvedValueOnce({
      status: 'cached',
      job_id: null,
      project_id: 'yt_subject_video',
      cache_hit: true,
      cache_scope: 'full_render',
      message: 'Hazir videolar bulundu. Mevcut sonuclar simdi getiriliyor.',
      gpu_locked: false,
    });
    const user = userEvent.setup();
    await renderJobForm();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /launch pipeline/i }));

    await waitFor(() => expect(mockRequestClipsRefresh).toHaveBeenCalledTimes(1));
    expect(mockRegisterQueuedJob).not.toHaveBeenCalled();
    expect(mockFetchJobs).not.toHaveBeenCalled();
    expect(screen.getByText(/hazir videolar bulundu/i)).toBeInTheDocument();
  });
});

describe('JobForm submission flow - cache and duration controls', () => {
  it('shows cache controls only after a processed video is detected', async () => {
    mockCacheStatus.mockResolvedValueOnce({
      project_id: 'yt_subject_video',
      project_cached: true,
      analysis_cached: true,
      render_cached: true,
      cache_scope: 'full_render',
      clip_count: 3,
      message: 'Bu video icin ayni ayarlarla hazir videolar bulundu.',
    });
    const user = userEvent.setup();
    await renderJobForm();

    expect(screen.queryByText(/cache intelligence/i)).not.toBeInTheDocument();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');

    await waitFor(() => expect(mockCacheStatus).toHaveBeenCalled());
    expect(await screen.findByText(/cache intelligence/i)).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: /refresh viral clip selection/i })).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: /regenerate videos/i })).toBeInTheDocument();
  });

  it('submits force flags from cache controls and keeps rerender enabled when reanalyze is selected', async () => {
    mockCacheStatus.mockResolvedValueOnce({
      project_id: 'yt_subject_video',
      project_cached: true,
      analysis_cached: true,
      render_cached: true,
      cache_scope: 'full_render',
      clip_count: 2,
      message: 'Bu video icin ayni ayarlarla hazir videolar bulundu.',
    });
    mockStart.mockResolvedValueOnce({
      status: 'queued',
      job_id: 'test',
      message: 'İşlem başlatılıyor. Hazırlık aşamaları yürütülüyor...',
      processing_locked: false,
      gpu_locked: false,
    });
    const user = userEvent.setup();
    await renderJobForm();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await screen.findByText(/cache intelligence/i);
    await user.click(screen.getByRole('switch', { name: /refresh viral clip selection/i }));
    expect(screen.getByRole('switch', { name: /regenerate videos/i })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('switch', { name: /regenerate videos/i })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: /launch pipeline/i }));

    expect(mockStart).toHaveBeenCalledWith(expect.objectContaining({
      force_reanalyze: true,
      force_rerender: true,
    }));
  });

  it('submits custom manual durations when auto mode is disabled', async () => {
    mockStart.mockResolvedValueOnce({ status: 'queued', job_id: 'test', message: 'queued', processing_locked: true, gpu_locked: false });
    const user = userEvent.setup();
    await renderJobForm();

    await user.click(screen.getByRole('switch', { name: /automatic mode/i }));
    fireEvent.change(screen.getByLabelText(/min duration/i), { target: { value: '45' } });
    fireEvent.change(screen.getByLabelText(/max duration/i), { target: { value: '90' } });
    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /launch pipeline/i }));

    expect(mockStart).toHaveBeenCalledWith(expect.objectContaining({
      auto_mode: false,
      duration_min: 45,
      duration_max: 90,
    }));
  });
});
