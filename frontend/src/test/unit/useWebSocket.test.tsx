import { act, render } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { useWebSocket } from '../../hooks/useWebSocket';

const authRuntimeState = {
  backendAuthStatus: 'fresh',
  canUseProtectedRequests: true,
};

const storeMock = {
  mergeJobTimelineEvent: vi.fn(),
  markClipReady: vi.fn(),
  fetchJobs: vi.fn(),
  setWsStatus: vi.fn(),
};

const getFreshTokenMock = vi.fn().mockResolvedValue(null);

vi.mock('../../store/useJobStore', () => ({
  useJobStore: () => storeMock,
}));

vi.mock('../../auth/runtime', () => ({
  useAuthRuntimeStore: Object.assign(
    (selector: (state: typeof authRuntimeState) => unknown) => selector(authRuntimeState),
    { getState: () => authRuntimeState },
  ),
}));

vi.mock('../../api/client', () => ({
  getFreshToken: (...args: unknown[]) => getFreshTokenMock(...args),
}));

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  protocols?: string | string[];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = protocols;
    FakeWebSocket.instances.push(this);
  }
  close() { this.onclose?.(); }
}

function TestComponent() { useWebSocket(); return <div />; }

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  FakeWebSocket.instances = [];
  authRuntimeState.backendAuthStatus = 'fresh';
  authRuntimeState.canUseProtectedRequests = true;
  getFreshTokenMock.mockResolvedValue(null);
  vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket);
});

describe('useWebSocket connection lifecycle', () => {
  it('fetches jobs immediately before websocket opens so refresh can restore visible state', async () => {
    render(<TestComponent />);
    await act(async () => {});

    expect(storeMock.fetchJobs).toHaveBeenCalledTimes(1);
  });

  it('reconnects and re-syncs jobs after disconnect', async () => {
    render(<TestComponent />);
    await act(async () => {});
    const ws = FakeWebSocket.instances[0];
    act(() => ws.onopen?.());
    expect(storeMock.fetchJobs).toHaveBeenCalledTimes(2);

    act(() => ws.onclose?.());
    act(() => vi.advanceTimersByTime(3000));
    await act(async () => {});
    const next = FakeWebSocket.instances[1];
    act(() => next.onopen?.());
    expect(storeMock.fetchJobs).toHaveBeenCalledTimes(3);
  });

  it('cleans reconnect timeout on unmount', async () => {
    const view = render(<TestComponent />);
    await act(async () => {});
    const ws = FakeWebSocket.instances[0];
    act(() => ws.onclose?.());
    view.unmount();
    act(() => vi.advanceTimersByTime(3000));
    expect(FakeWebSocket.instances).toHaveLength(1);
  });
});

describe('useWebSocket message handling', () => {
  it('validates incoming message schema before updating store', async () => {
    render(<TestComponent />);
    await act(async () => {});
    const ws = FakeWebSocket.instances[0];
    act(() => ws.onmessage?.({ data: JSON.stringify({ foo: 'bar' }) }));
    expect(storeMock.mergeJobTimelineEvent).not.toHaveBeenCalled();

    act(() => ws.onmessage?.({
      data: JSON.stringify({
        event_id: 'evt-1',
        at: '2026-03-20T00:00:00.000Z',
        job_id: 'j1',
        message: 'ok',
        progress: 10,
        source: 'worker',
      }),
    }));
    expect(storeMock.mergeJobTimelineEvent).toHaveBeenCalledWith({
      at: '2026-03-20T00:00:00.000Z',
      event_id: 'evt-1',
      job_id: 'j1',
      message: 'ok',
      progress: 10,
      source: 'worker',
      status: undefined,
      download_progress: undefined,
    });
  });

  it('passes structured download progress through to the store', async () => {
    render(<TestComponent />);
    await act(async () => {});
    const ws = FakeWebSocket.instances[0];

    act(() => ws.onmessage?.({
      data: JSON.stringify({
        event_id: 'evt-download-1',
        at: '2026-03-20T00:00:05.000Z',
        job_id: 'j-download',
        message: 'indiriliyor',
        progress: 15,
        status: 'processing',
        download_progress: {
          phase: 'download',
          downloaded_bytes: 1024,
          total_bytes: 2048,
          percent: 50,
          speed_text: '1.00MiB/s',
          eta_text: '00:03',
          status: 'downloading',
        },
      }),
    }));

    expect(storeMock.mergeJobTimelineEvent).toHaveBeenCalledWith({
      at: '2026-03-20T00:00:05.000Z',
      event_id: 'evt-download-1',
      job_id: 'j-download',
      message: 'indiriliyor',
      progress: 15,
      source: 'worker',
      status: 'processing',
      download_progress: {
        phase: 'download',
        downloaded_bytes: 1024,
        total_bytes: 2048,
        percent: 50,
        speed_text: '1.00MiB/s',
        eta_text: '00:03',
        status: 'downloading',
      },
    });
  });

  it('marks clip-ready signals when websocket payload announces a ready clip', async () => {
    render(<TestComponent />);
    await act(async () => {});
    const ws = FakeWebSocket.instances[0];

    act(() => ws.onmessage?.({
      data: JSON.stringify({
        event_type: 'clip_ready',
        event_id: 'clip-ready-1',
        at: '2026-03-20T00:00:01.000Z',
        job_id: 'manual_1',
        message: 'Klip hazir',
        progress: 91,
        status: 'processing',
        source: 'clip_ready',
        project_id: 'proj-1',
        clip_name: 'clip-1.mp4',
        ui_title: 'Hook',
      }),
    }));

    expect(storeMock.mergeJobTimelineEvent).toHaveBeenCalledWith({
      at: '2026-03-20T00:00:01.000Z',
      event_id: 'clip-ready-1',
      job_id: 'manual_1',
      message: 'Klip hazir',
      progress: 91,
      source: 'clip_ready',
      status: 'processing',
      download_progress: undefined,
    });
    expect(storeMock.markClipReady).toHaveBeenCalledWith({
      at: '2026-03-20T00:00:01.000Z',
      clipName: 'clip-1.mp4',
      job_id: 'manual_1',
      message: 'Klip hazir',
      progress: 91,
      projectId: 'proj-1',
      uiTitle: 'Hook',
    });
  });
});

describe('useWebSocket auth gating', () => {
  it('uses websocket subprotocol auth when token is present', async () => {
    getFreshTokenMock.mockResolvedValueOnce('jwt-token');
    render(<TestComponent />);
    await act(async () => {});
    const ws = FakeWebSocket.instances[0];
    expect(ws.url).toContain('/ws/progress');
    expect(ws.protocols).toEqual(['bearer', 'jwt-token']);
  });

  it('marks store as disconnected when hook is disabled', async () => {
    function DisabledComponent() {
      useWebSocket(false);
      return <div />;
    }

    render(<DisabledComponent />);
    await act(async () => {});

    expect(storeMock.setWsStatus).toHaveBeenCalledWith('disconnected');
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it('does not connect while protected requests are paused', async () => {
    authRuntimeState.backendAuthStatus = 'paused';
    authRuntimeState.canUseProtectedRequests = false;

    render(<TestComponent />);
    await act(async () => {});

    expect(storeMock.setWsStatus).toHaveBeenCalledWith('disconnected');
    expect(getFreshTokenMock).not.toHaveBeenCalled();
    expect(FakeWebSocket.instances).toHaveLength(0);
  });
});

describe('useWebSocket reconnect cancellation', () => {
  it('cancels pending reconnects when auth becomes paused', async () => {
    const view = render(<TestComponent />);
    await act(async () => {});
    const ws = FakeWebSocket.instances[0];

    act(() => ws.onclose?.());

    authRuntimeState.backendAuthStatus = 'paused';
    authRuntimeState.canUseProtectedRequests = false;
    view.rerender(<TestComponent />);

    act(() => vi.advanceTimersByTime(3000));

    expect(FakeWebSocket.instances).toHaveLength(1);
  });
});
