import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../../i18n';

const authRuntimeState = {
  backendAuthStatus: 'fresh' as 'fresh' | 'paused' | 'refreshing',
  canUseProtectedRequests: true,
  pauseReason: null as string | null,
};

const storeState = {
  jobs: [] as Array<{
    job_id: string;
    status: string;
    progress: number;
    last_message: string;
    created_at: number;
    download_progress?: {
      phase: 'download';
      downloaded_bytes?: number;
      total_bytes?: number;
      percent?: number;
      speed_text?: string;
      eta_text?: string;
      status?: string;
    };
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
  hasRetainedHistory: true,
  jobHistoryExpiresAt: null as number | null,
  clearRetainedHistory: vi.fn(),
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
    authRuntimeState.canUseProtectedRequests = true;
    authRuntimeState.pauseReason = null;
    storeState.wsStatus = 'connected';
    storeState.clearRetainedHistory.mockReset();
    storeState.hasRetainedHistory = true;
    storeState.jobHistoryExpiresAt = null;
    storeState.jobs = [
      {
        job_id: 'job-1',
        status: 'processing',
        progress: 40,
        last_message: 'fourth log',
        created_at: 1,
        download_progress: {
          phase: 'download',
          downloaded_bytes: 1048576,
          total_bytes: 2097152,
          percent: 50,
          speed_text: '1.00MiB/s',
          eta_text: '00:03',
          status: 'downloading',
        },
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

  it('shows download summary in the terminal chrome when active job is downloading', async () => {
    const { HoloTerminal } = await import('../../components/HoloTerminal');
    render(<HoloTerminal compact />);

    expect(screen.getByText(/1.0 MiB \/ 2.0 MiB/i)).toBeInTheDocument();
    expect(screen.getByText(/ETA 00:03/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /clear history/i })).toBeDisabled();
  });

  it('replaces handshake empty state with auth pause messaging', async () => {
    authRuntimeState.backendAuthStatus = 'paused';
    authRuntimeState.canUseProtectedRequests = false;
    authRuntimeState.pauseReason = 'token_expired';
    storeState.wsStatus = 'connecting';
    storeState.hasRetainedHistory = false;
    storeState.jobs = [];

    const { HoloTerminal } = await import('../../components/HoloTerminal');
    render(<HoloTerminal compact />);

    expect(screen.getByText('WS:DISCONNECTED')).toBeInTheDocument();
    expect(screen.getByText(/Auth refresh required before live logs can resume\./i)).toBeInTheDocument();
    expect(screen.queryByText(/Waiting for system handshake/i)).not.toBeInTheDocument();
  });

  it('shows fallback auth messaging when cached protected access is still usable', async () => {
    authRuntimeState.backendAuthStatus = 'paused';
    authRuntimeState.canUseProtectedRequests = true;
    authRuntimeState.pauseReason = 'auth_provider_unavailable';
    storeState.wsStatus = 'connecting';
    storeState.hasRetainedHistory = false;
    storeState.jobs = [];

    const { HoloTerminal } = await import('../../components/HoloTerminal');
    render(<HoloTerminal compact />);

    expect(screen.getByText('AUTH:FALLBACK')).toBeInTheDocument();
    expect(screen.getByText(/cached auth still allows protected api access/i)).toBeInTheDocument();
  });

  it('renders Turkish terminal chrome labels in tr locale', async () => {
    await i18n.changeLanguage('tr');
    authRuntimeState.backendAuthStatus = 'paused';
    authRuntimeState.canUseProtectedRequests = false;
    authRuntimeState.pauseReason = 'token_expired';
    storeState.wsStatus = 'connecting';
    storeState.hasRetainedHistory = false;
    storeState.jobs = [];

    const { HoloTerminal } = await import('../../components/HoloTerminal');
    render(<HoloTerminal compact />);

    expect(screen.getByText('Çekirdek Loglar')).toBeInTheDocument();
    expect(screen.getByText('WS:BAĞLANTI KESİLDİ')).toBeInTheDocument();
    expect(screen.getByText('AUTH:TOKEN-SÜRESİ-DOLDU')).toBeInTheDocument();
    expect(screen.getByText(/auth yenilemesi gerekiyor/i)).toBeInTheDocument();
  });

  it('shows retention countdown and clears retained history when no active jobs remain', async () => {
    const user = userEvent.setup();
    storeState.jobHistoryExpiresAt = Date.now() + 5 * 60 * 1000;
    storeState.jobs = [
      {
        job_id: 'job-1',
        status: 'completed',
        progress: 100,
        last_message: 'completed log',
        created_at: 1,
        timeline: [
          { id: 'evt-1', at: '2026-03-20T10:00:00.000Z', job_id: 'job-1', status: 'completed', progress: 100, message: 'completed log', source: 'worker' },
        ],
      },
    ];

    const { HoloTerminal } = await import('../../components/HoloTerminal');
    render(<HoloTerminal compact />);

    expect(screen.getByText(/Auto clear in/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /clear history/i }));
    expect(storeState.clearRetainedHistory).toHaveBeenCalledTimes(1);
  });
});
