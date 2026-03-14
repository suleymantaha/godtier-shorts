import { act, render } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { useWebSocket } from '../../hooks/useWebSocket';

const storeMock = {
  updateJobProgress: vi.fn(),
  fetchJobs: vi.fn(),
  setWsStatus: vi.fn(),
};

const getFreshTokenMock = vi.fn().mockResolvedValue(null);

vi.mock('../../store/useJobStore', () => ({
  useJobStore: () => storeMock,
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
});
