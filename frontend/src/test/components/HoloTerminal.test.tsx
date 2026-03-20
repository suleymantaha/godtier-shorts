import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authRuntimeState = {
  backendAuthStatus: 'fresh' as 'fresh' | 'paused' | 'refreshing',
  pauseReason: null as string | null,
};

const storeState = {
  jobs: [] as Array<{
    job_id: string;
    status: string;
    progress: number;
    last_message: string;
    created_at: number;
    timeline?: Array<{
      id: string;
      at: string;
      job_id: string;
      status: 'queued' | 'processing' | 'completed' | 'cancelled' | 'error' | 'empty';
      progress: number;
      message: string;
      source: 'api' | 'worker' | 'websocket' | 'clip_ready';
    }>;
  }>,
  wsStatus: 'connected' as 'connecting' | 'connected' | 'reconnecting' | 'disconnected',
};

vi.mock('../../auth/runtime', () => ({
  useAuthRuntimeStore: (selector: (state: typeof authRuntimeState) => unknown) => selector(authRuntimeState),
}));

vi.mock('../../store/useJobStore', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../store/useJobStore')>();
  return {
    ...actual,
    useJobStore: () => storeState,
  };
});

describe('HoloTerminal', () => {
  beforeEach(() => {
    authRuntimeState.backendAuthStatus = 'fresh';
    authRuntimeState.pauseReason = null;
    storeState.wsStatus = 'connected';
    storeState.jobs = [
      {
        job_id: 'job-1',
        status: 'processing',
        progress: 40,
        last_message: 'fourth log',
        created_at: 1,
        timeline: [
          { id: 'evt-1', at: '2026-03-20T10:00:00.000Z', job_id: 'job-1', status: 'processing', progress: 10, message: 'first log', source: 'worker' },
          { id: 'evt-2', at: '2026-03-20T10:00:01.000Z', job_id: 'job-1', status: 'processing', progress: 20, message: 'second log', source: 'worker' },
          { id: 'evt-3', at: '2026-03-20T10:00:02.000Z', job_id: 'job-1', status: 'processing', progress: 30, message: 'third log', source: 'worker' },
          { id: 'evt-4', at: '2026-03-20T10:00:03.000Z', job_id: 'job-1', status: 'processing', progress: 40, message: 'fourth log', source: 'worker' },
        ],
      },
    ];
  });

  it('keeps compact view limited to latest 3 logs', async () => {
    const { HoloTerminal } = await import('../../components/HoloTerminal');
    render(<HoloTerminal compact />);

    expect(screen.queryByText(/>>> first log/i)).not.toBeInTheDocument();
    expect(screen.getByText(/>>> second log/i)).toBeInTheDocument();
    expect(screen.getByText(/>>> third log/i)).toBeInTheDocument();
    expect(screen.getAllByText(/>>> fourth log/i).length).toBeGreaterThan(0);
  });

  it('shows full log history in expanded view', async () => {
    const user = userEvent.setup();
    const { HoloTerminal } = await import('../../components/HoloTerminal');
    render(<HoloTerminal compact />);

    await user.click(screen.getByRole('button', { name: /expand logs/i }));

    expect(screen.getByRole('dialog', { name: /core logs history/i })).toBeInTheDocument();
    expect(screen.getByText(/>>> first log/i)).toBeInTheDocument();
  });

  it('updates ws/auth labels for token-expired pause state', async () => {
    const { HoloTerminal } = await import('../../components/HoloTerminal');
    const view = render(<HoloTerminal compact />);

    expect(screen.getByText('WS:CONNECTED')).toBeInTheDocument();
    expect(screen.getByText('AUTH:READY')).toBeInTheDocument();

    storeState.wsStatus = 'reconnecting';
    authRuntimeState.backendAuthStatus = 'paused';
    authRuntimeState.pauseReason = 'token_expired';
    view.rerender(<HoloTerminal compact />);

    expect(screen.getByText('WS:DISCONNECTED')).toBeInTheDocument();
    expect(screen.getByText('AUTH:TOKEN-EXPIRED')).toBeInTheDocument();
  });

  it('replaces handshake empty state with auth pause messaging', async () => {
    authRuntimeState.backendAuthStatus = 'paused';
    authRuntimeState.pauseReason = 'token_expired';
    storeState.wsStatus = 'connecting';
    storeState.jobs = [];

    const { HoloTerminal } = await import('../../components/HoloTerminal');
    render(<HoloTerminal compact />);

    expect(screen.getByText('WS:DISCONNECTED')).toBeInTheDocument();
    expect(screen.getByText(/Auth refresh required before live logs can resume\./i)).toBeInTheDocument();
    expect(screen.queryByText(/Waiting for system handshake/i)).not.toBeInTheDocument();
  });
});
