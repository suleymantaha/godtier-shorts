import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const storeState = {
  jobs: [],
  cancelJob: vi.fn(),
  lastError: null as string | null,
  clearError: vi.fn(),
};

vi.mock('../../store/useJobStore', () => ({
  useJobStore: () => storeState,
}));

describe('JobQueue', () => {
  it('shows download progress details and preserves FIFO order', async () => {
    storeState.jobs = [
      {
        job_id: 'queued-2',
        url: 'https://youtube.com/watch?v=queued2',
        style: 'TIKTOK',
        status: 'queued',
        progress: 0,
        last_message: 'İşlem sırası bekleniyor...',
        created_at: 20,
      },
      {
        job_id: 'processing-1',
        url: 'https://youtube.com/watch?v=processing1',
        style: 'TIKTOK',
        status: 'processing',
        progress: 15,
        last_message: 'indiriliyor',
        created_at: 10,
        download_progress: {
          phase: 'download',
          downloaded_bytes: 1048576,
          total_bytes: 2097152,
          percent: 50,
          speed_text: '1.00MiB/s',
          eta_text: '00:03',
          status: 'downloading',
        },
      },
    ];

    const { JobQueue } = await import('../../components/JobQueue');
    const { container } = render(<JobQueue />);

    expect(screen.getByText(/1.0 MiB \/ 2.0 MiB/i)).toBeInTheDocument();
    expect(screen.getByText(/50.0%/i)).toBeInTheDocument();
    expect(screen.getByText(/ETA 00:03/i)).toBeInTheDocument();
    expect(screen.getByText(/Current Job/i)).toBeInTheDocument();
    expect(screen.getByText('processing-1')).toBeInTheDocument();
    expect(screen.getByText(/Queued Jobs/i)).toBeInTheDocument();
    expect(screen.getByText(/^1$/)).toBeInTheDocument();
    expect(screen.getByText(/İşlem sırası bekleniyor/i)).toBeInTheDocument();

    const content = container.textContent ?? '';
    expect(content.indexOf('processing-1')).toBeLessThan(content.indexOf('queued-2'));
  });

  it('requires a second click before cancelling a job', async () => {
    storeState.cancelJob.mockClear();
    storeState.jobs = [
      {
        job_id: 'processing-1',
        url: 'https://youtube.com/watch?v=processing1',
        style: 'TIKTOK',
        status: 'processing',
        progress: 15,
        last_message: 'indiriliyor',
        created_at: 10,
      },
    ];

    const { JobQueue } = await import('../../components/JobQueue');
    render(<JobQueue />);

    fireEvent.click(screen.getByLabelText(/Cancel job/i));
    expect(storeState.cancelJob).not.toHaveBeenCalled();
    expect(screen.getByText(/Click again to confirm cancellation\./i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/Confirm cancel/i));
    expect(storeState.cancelJob).toHaveBeenCalledWith('processing-1');
  });
});
