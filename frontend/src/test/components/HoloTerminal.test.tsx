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
  }>,
  logs: [] as Array<{ message: string; progress: number; timestamp: string }>,
  wsStatus: 'connected' as 'connecting' | 'connected' | 'reconnecting' | 'disconnected',
};

vi.mock('../../auth/runtime', () => ({
  useAuthRuntimeStore: (selector: (state: typeof authRuntimeState) => unknown) => selector(authRuntimeState),
}));

vi.mock('../../store/useJobStore', () => ({
  useJobStore: () => storeState,
}));

describe('HoloTerminal', () => {
  beforeEach(() => {
    authRuntimeState.backendAuthStatus = 'fresh';
    authRuntimeState.pauseReason = null;
    storeState.wsStatus = 'connected';
    storeState.jobs = [];
    storeState.logs = [
      { message: '[job-1] first log', progress: 10, timestamp: '10:00:00' },
      { message: '[job-1] second log', progress: 20, timestamp: '10:00:01' },
      { message: '[job-1] third log', progress: 30, timestamp: '10:00:02' },
      { message: '[job-1] fourth log', progress: 40, timestamp: '10:00:03' },
    ];
  });

  it('keeps compact view limited to latest 3 logs', async () => {
    const { HoloTerminal } = await import('../../components/HoloTerminal');
    render(<HoloTerminal compact />);

    expect(screen.queryByText(/\[job-1\] first log/i)).not.toBeInTheDocument();
    expect(screen.getByText(/\[job-1\] second log/i)).toBeInTheDocument();
    expect(screen.getByText(/\[job-1\] third log/i)).toBeInTheDocument();
    expect(screen.getAllByText(/\[job-1\] fourth log/i).length).toBeGreaterThan(0);
  });

  it('shows full log history in expanded view', async () => {
    const user = userEvent.setup();
    const { HoloTerminal } = await import('../../components/HoloTerminal');
    render(<HoloTerminal compact />);

    await user.click(screen.getByRole('button', { name: /expand logs/i }));

    expect(screen.getByRole('dialog', { name: /core logs history/i })).toBeInTheDocument();
    expect(screen.getByText(/\[job-1\] first log/i)).toBeInTheDocument();
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

    expect(screen.getByText('WS:RECONNECTING')).toBeInTheDocument();
    expect(screen.getByText('AUTH:TOKEN-EXPIRED')).toBeInTheDocument();
  });
});
