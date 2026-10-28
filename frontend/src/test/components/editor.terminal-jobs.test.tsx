import { act, renderHook } from '@testing-library/react';
import type { ChangeEvent } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useEditorController } from '../../components/editor/useEditorController';
import type { Job } from '../../types';

const store = vi.hoisted(() => ({ jobs: [] as Job[] }));
vi.mock('../../store/useJobStore', () => ({ useJobStore: () => store }));
vi.mock('../../api/client', () => ({
  clipsApi: { upload: vi.fn().mockResolvedValue({ job_id: 'upload_1', project_id: 'p1' }) },
  editorApi: {
    getTranscript: vi.fn().mockResolvedValue({ transcript: [] }),
    processBatch: vi.fn().mockResolvedValue({ job_id: 'manual_1' }),
  },
}));

describe('Editor terminal jobs', () => {
  beforeEach(() => {
    localStorage.clear();
    store.jobs = [];
    URL.createObjectURL = vi.fn(() => 'blob:preview');
    URL.revokeObjectURL = vi.fn();
  });

  it.each(['review_required', 'empty'] as const)('releases render and transcription busy state for %s', async (status) => {
    const { result, rerender } = renderHook(() => useEditorController({}));
    await act(async () => { await result.current.handleProcessBatch(); });
    expect(result.current.processing).toBe(true);
    store.jobs = [{ job_id: 'manual_1', url: '', style: 'HORMOZI', status, progress: 100, last_message: 'Needs attention', created_at: 1 }];
    rerender();
    expect(result.current.processing).toBe(false);
    expect(result.current.error).toBe('Needs attention');

    await act(async () => {
      await result.current.handleFileUpload({ target: { files: [new File(['x'], 'video.mp4')], value: '' } } as unknown as ChangeEvent<HTMLInputElement>);
    });
    expect(result.current.transcribing).toBe(true);
    store.jobs = [{ ...store.jobs[0], job_id: 'upload_1' }];
    rerender();
    expect(result.current.transcribing).toBe(false);
    expect(result.current.error).toBe('Needs attention');
  });
});
