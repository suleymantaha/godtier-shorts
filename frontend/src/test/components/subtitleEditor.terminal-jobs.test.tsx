import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SUBTITLE_SESSION_STORAGE_KEY } from '../../app/helpers';
import { useSubtitleJobTrackingEffect } from '../../components/subtitleEditor/jobs';

describe('SubtitleEditor terminal jobs', () => {
  it.each(['review_required', 'empty'] as const)('releases saving and clears tracked session for %s without claiming success', (status) => {
    localStorage.setItem(SUBTITLE_SESSION_STORAGE_KEY, '{}');
    const setSaving = vi.fn();
    const setError = vi.fn();
    const setSuccessMessage = vi.fn();
    const fetchJobs = vi.fn().mockResolvedValue(undefined);
    renderHook(() => useSubtitleJobTrackingEffect({
      currentJob: { job_id: 'manual_1', url: '', style: 'HORMOZI', status, progress: 100, last_message: 'Needs attention', created_at: 1 },
      fetchJobs, loadTranscript: vi.fn().mockResolvedValue(undefined), mode: 'project', selectedClip: null,
      selectionKey: 'project:p1', setCacheBust: vi.fn(), setError, setSaving, setSuccessMessage,
    }));
    expect(setSaving).toHaveBeenCalledWith(false);
    expect(setError).toHaveBeenCalledWith('Needs attention');
    expect(setSuccessMessage).not.toHaveBeenCalledWith(expect.any(String));
    expect(localStorage.getItem(SUBTITLE_SESSION_STORAGE_KEY)).toBeNull();
    expect(fetchJobs).toHaveBeenCalledTimes(1);
  });
});
