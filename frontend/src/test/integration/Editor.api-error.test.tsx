import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import { Editor } from '../../components/Editor';

vi.mock('../../store/useJobStore', () => ({ useJobStore: () => ({ jobs: [] }) }));
vi.mock('../../api/client', () => ({
  clipsApi: {
    upload: vi.fn().mockResolvedValue({ status: 'uploaded', job_id: 'u1', project_id: 'p1' }),
    getTranscript: vi.fn().mockResolvedValue({ transcript: [] }),
  },
  editorApi: {
    getTranscript: vi.fn().mockResolvedValue({ transcript: [] }),
    saveTranscript: vi.fn().mockResolvedValue({ status: 'success' }),
    processBatch: vi.fn().mockRejectedValue(new Error('API down')),
    processManual: vi.fn().mockResolvedValue({ status: 'started', job_id: 'm1' }),
    reburn: vi.fn().mockResolvedValue({ status: 'started', job_id: 'r1' }),
  },
}));

describe('Editor API error rendering', () => {
  it('shows alert when batch API fails', async () => {
    render(<Editor mode="master" />);
    const video = document.querySelector('video') as HTMLVideoElement;
    if (video) {
      Object.defineProperty(video, 'duration', { configurable: true, value: 120 });
      fireEvent.loadedMetadata(video);
    }
    const button = screen.getByRole('button', { name: /AI ILE TOPLU ÜRET/i });
    fireEvent.click(button);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('API down');
    });
  });
});
