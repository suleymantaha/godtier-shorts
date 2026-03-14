import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  MAX_WEBSOCKET_RETRY,
  createProgressWebSocket,
  getConnectStatus,
  getReconnectState,
  parseProgressMessage,
} from '../../hooks/useWebSocket.helpers';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  protocols?: string | string[];

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = protocols;
    FakeWebSocket.instances.push(this);
  }
}

describe('useWebSocket helpers', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket);
  });

  it('returns the expected connect status from retry count', () => {
    expect(getConnectStatus(0)).toBe('connecting');
    expect(getConnectStatus(2)).toBe('reconnecting');
  });

  it('computes reconnect state until max retry is reached', () => {
    expect(getReconnectState(0)).toEqual({
      nextRetryCount: 1,
      shouldReconnect: true,
      status: 'reconnecting',
    });

    expect(getReconnectState(MAX_WEBSOCKET_RETRY - 1)).toEqual({
      nextRetryCount: MAX_WEBSOCKET_RETRY,
      shouldReconnect: false,
      status: 'disconnected',
    });
  });

  it('creates websocket with bearer subprotocol when token is present', () => {
    const ws = createProgressWebSocket('jwt-token', 'ws://localhost:8000');

    expect(ws).toBe(FakeWebSocket.instances[0]);
    expect(FakeWebSocket.instances[0].url).toBe('ws://localhost:8000/ws/progress');
    expect(FakeWebSocket.instances[0].protocols).toEqual(['bearer', 'jwt-token']);
  });

  it('parses only valid progress messages', () => {
    expect(parseProgressMessage(JSON.stringify({ foo: 'bar' }))).toBeNull();
    expect(parseProgressMessage(JSON.stringify({ job_id: 'job-1', message: 'ok', progress: 42 }))).toEqual({
      job_id: 'job-1',
      message: 'ok',
      progress: 42,
      status: undefined,
    });
  });

  it('returns null on invalid json payloads', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(parseProgressMessage('{not-json')).toBeNull();
    expect(errorSpy).toHaveBeenCalled();
  });
});
