import { act, render } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { useWebSocket } from '../../hooks/useWebSocket';

const authRuntimeState = {
  backendAuthStatus: 'fresh',
  canUseProtectedRequests: true,
};

const storeMock = {
  updateJobProgress: vi.fn(),
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

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    FakeWebSocket.instances = [];
    authRuntimeState.backendAuthStatus = 'fresh';
    authRuntimeState.canUseProtectedRequests = true;
    getFreshTokenMock.mockResolvedValue(null);
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket);
  });

  it('reconnects and re-syncs jobs after disconnect', async () => {
    render(<TestComponent />);
    await act(async () => {});
    const ws = FakeWebSocket.instances[0];
    act(() => ws.onopen?.());
    expect(storeMock.fetchJobs).toHaveBeenCalledTimes(1);

    act(() => ws.onclose?.());
    act(() => vi.advanceTimersByTime(3000));
    await act(async () => {});
    const next = FakeWebSocket.instances[1];
    act(() => next.onopen?.());
    expect(storeMock.fetchJobs).toHaveBeenCalledTimes(2);
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

  it('validates incoming message schema before updating store', async () => {
    render(<TestComponent />);
    await act(async () => {});
    const ws = FakeWebSocket.instances[0];
    act(() => ws.onmessage?.({ data: JSON.stringify({ foo: 'bar' }) }));
    expect(storeMock.updateJobProgress).not.toHaveBeenCalled();

    act(() => ws.onmessage?.({ data: JSON.stringify({ job_id: 'j1', message: 'ok', progress: 10 }) }));
    expect(storeMock.updateJobProgress).toHaveBeenCalledWith('j1', 'ok', 10, undefined);
  });

  it('marks clip-ready signals when websocket payload announces a ready clip', async () => {
    render(<TestComponent />);
    await act(async () => {});
    const ws = FakeWebSocket.instances[0];

    act(() => ws.onmessage?.({
      data: JSON.stringify({
        event_type: 'clip_ready',
        job_id: 'manual_1',
        message: 'Klip hazir',
        progress: 91,
        status: 'processing',
        project_id: 'proj-1',
        clip_name: 'clip-1.mp4',
        ui_title: 'Hook',
      }),
    }));

    expect(storeMock.updateJobProgress).toHaveBeenCalledWith('manual_1', 'Klip hazir', 91, 'processing');
    expect(storeMock.markClipReady).toHaveBeenCalledWith({
      clipName: 'clip-1.mp4',
      job_id: 'manual_1',
      message: 'Klip hazir',
      progress: 91,
      projectId: 'proj-1',
      uiTitle: 'Hook',
    });
  });

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
