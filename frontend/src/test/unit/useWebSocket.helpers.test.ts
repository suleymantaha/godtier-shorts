import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  MAX_WEBSOCKET_RETRY,
  createProgressWebSocket,
  getWsParseTelemetrySnapshot,
  getConnectStatus,
  getReconnectState,
  parseProgressMessage,
  resetWsParseTelemetry,
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

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket);
  resetWsParseTelemetry();
});

describe('useWebSocket helpers - connection state', () => {
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
});

describe('useWebSocket helpers - payload parsing success cases', () => {
  it('parses only valid progress messages', () => {
    expect(parseProgressMessage(JSON.stringify({ foo: 'bar' }))).toBeNull();
    expect(parseProgressMessage(JSON.stringify({
      event_id: 'evt-1',
      at: '2026-03-20T00:00:00.000Z',
      job_id: 'job-1',
      message: 'ok',
      progress: 42,
      source: 'worker',
    }))).toEqual({
      event_type: 'progress',
      event_id: 'evt-1',
      at: '2026-03-20T00:00:00.000Z',
      job_id: 'job-1',
      message: 'ok',
      progress: 42,
      status: undefined,
      source: 'worker',
      download_progress: undefined,
      project_id: undefined,
      clip_name: undefined,
      ui_title: undefined,
    });
  });

  it('parses clip_ready payloads with optional fields', () => {
    expect(parseProgressMessage(JSON.stringify({
      event_type: 'clip_ready',
      event_id: 'clip-ready-1',
      at: '2026-03-20T00:00:02.000Z',
      job_id: 'manual_1',
      message: 'Klip hazir',
      progress: 88,
      status: 'processing',
      source: 'clip_ready',
      project_id: 'proj-1',
      clip_name: 'clip-1.mp4',
      ui_title: 'Hook',
    }))).toEqual({
      event_type: 'clip_ready',
      event_id: 'clip-ready-1',
      at: '2026-03-20T00:00:02.000Z',
      job_id: 'manual_1',
      message: 'Klip hazir',
      progress: 88,
      status: 'processing',
      source: 'clip_ready',
      download_progress: undefined,
      project_id: 'proj-1',
      clip_name: 'clip-1.mp4',
      ui_title: 'Hook',
    });
  });

  it('parses optional download progress metadata', () => {
    expect(parseProgressMessage(JSON.stringify({
      event_id: 'evt-download-1',
      at: '2026-03-20T00:00:03.000Z',
      job_id: 'job-download',
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
    }))).toEqual({
      event_type: 'progress',
      event_id: 'evt-download-1',
      at: '2026-03-20T00:00:03.000Z',
      job_id: 'job-download',
      message: 'indiriliyor',
      progress: 15,
      status: 'processing',
      source: 'worker',
      download_progress: {
        phase: 'download',
        downloaded_bytes: 1024,
        total_bytes: 2048,
        percent: 50,
        speed_text: '1.00MiB/s',
        eta_text: '00:03',
        status: 'downloading',
      },
      project_id: undefined,
      clip_name: undefined,
      ui_title: undefined,
    });
  });
});

describe('useWebSocket helpers - payload parsing failures', () => {
  it('returns null on invalid json payloads', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(parseProgressMessage('{not-json')).toBeNull();
    expect(errorSpy).toHaveBeenCalled();
  });

  it('tracks parse/drop telemetry counters for invalid payloads', () => {
    expect(parseProgressMessage(JSON.stringify({ message: 'missing id', progress: 10 }))).toBeNull();
    expect(parseProgressMessage(JSON.stringify({ job_id: 'job-1', message: 123, progress: 10 }))).toBeNull();
    expect(parseProgressMessage(JSON.stringify({
      event_id: 'evt-2',
      at: '2026-03-20T00:00:01.000Z',
      job_id: 'job-2',
      message: 'ok',
      progress: 10,
    }))).toEqual({
      event_type: 'progress',
      event_id: 'evt-2',
      at: '2026-03-20T00:00:01.000Z',
      job_id: 'job-2',
      message: 'ok',
      progress: 10,
      status: undefined,
      source: 'worker',
      download_progress: undefined,
      project_id: undefined,
      clip_name: undefined,
      ui_title: undefined,
    });

    expect(getWsParseTelemetrySnapshot()).toEqual({
      parsed: 1,
      dropped: 2,
      droppedMissingJobId: 1,
      droppedInvalidSchema: 1,
      parseErrors: 0,
    });
  });
});
