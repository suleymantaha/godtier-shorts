import { act, render } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import React from 'react';

import { useWebSocket } from '../../hooks/useWebSocket';

const storeMock = {
  updateJobProgress: vi.fn(),
  fetchJobs: vi.fn(),
  setWsStatus: vi.fn(),
};

vi.mock('../../store/useJobStore', () => ({
  useJobStore: () => storeMock,
}));

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) { FakeWebSocket.instances.push(this); }
  close() { this.onclose?.(); }
}

function TestComponent() { useWebSocket(); return <div />; }

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket);
  });

  it('reconnects and re-syncs jobs after disconnect', () => {
    render(<TestComponent />);
    const ws = FakeWebSocket.instances[0];
    act(() => ws.onopen?.());
    expect(storeMock.fetchJobs).toHaveBeenCalledTimes(2);

    act(() => ws.onclose?.());
    act(() => vi.advanceTimersByTime(3000));
    const next = FakeWebSocket.instances[1];
    act(() => next.onopen?.());
    expect(storeMock.fetchJobs).toHaveBeenCalledTimes(3);
  });

  it('cleans reconnect timeout on unmount', () => {
    const view = render(<TestComponent />);
    const ws = FakeWebSocket.instances[0];
    act(() => ws.onclose?.());
    view.unmount();
    act(() => vi.advanceTimersByTime(3000));
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it('validates incoming message schema before updating store', () => {
    render(<TestComponent />);
    const ws = FakeWebSocket.instances[0];
    act(() => ws.onmessage?.({ data: JSON.stringify({ foo: 'bar' }) }));
    expect(storeMock.updateJobProgress).not.toHaveBeenCalled();

    act(() => ws.onmessage?.({ data: JSON.stringify({ job_id: 'j1', message: 'ok', progress: 10 }) }));
    expect(storeMock.updateJobProgress).toHaveBeenCalledWith('j1', 'ok', 10);
  });
});
