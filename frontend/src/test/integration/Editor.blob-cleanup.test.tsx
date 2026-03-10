import { fireEvent, render } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { Editor } from '../../components/Editor';

const uploadMock = vi.fn();

vi.mock('../../store/useJobStore', () => ({ useJobStore: () => ({ jobs: [] }) }));
vi.mock('../../api/client', () => ({
  clipsApi: {
    upload: (...args: unknown[]) => uploadMock(...args),
    getTranscript: vi.fn().mockResolvedValue({ transcript: [] }),
  },
  editorApi: {
    getTranscript: vi.fn().mockResolvedValue({ transcript: [] }),
    saveTranscript: vi.fn().mockResolvedValue({ status: 'success' }),
    processBatch: vi.fn().mockResolvedValue({ status: 'started', job_id: 'b1' }),
    processManual: vi.fn().mockResolvedValue({ status: 'started', job_id: 'm1' }),
    reburn: vi.fn().mockResolvedValue({ status: 'started', job_id: 'r1' }),
  },
}));

describe('Editor blob URL cleanup', () => {
  beforeEach(() => {
    uploadMock.mockResolvedValue({ status: 'uploaded', job_id: 'u1', project_id: 'p1' });
  });

  it('revokes previous object URL on new upload and unmount', async () => {
    const createSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValueOnce('blob:a').mockReturnValueOnce('blob:b');
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    const view = render(<Editor mode="master" />);
    const input = view.container.querySelector('input[type="file"]') as HTMLInputElement;
    const f1 = new File(['a'], 'a.mp4', { type: 'video/mp4' });
    const f2 = new File(['b'], 'b.mp4', { type: 'video/mp4' });
    fireEvent.change(input, { target: { files: [f1] } });
    fireEvent.change(input, { target: { files: [f2] } });

    expect(revokeSpy).toHaveBeenCalledWith('blob:a');
    view.unmount();
    expect(revokeSpy).toHaveBeenCalledWith('blob:b');
    createSpy.mockRestore();
    revokeSpy.mockRestore();
  });
});
