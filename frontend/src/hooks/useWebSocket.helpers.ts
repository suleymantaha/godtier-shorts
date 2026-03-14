import type { Job, WsStatus } from '../types';

export const MAX_WEBSOCKET_RETRY = 60;
export const RETRY_DELAY_MS = 3000;

interface ProgressMessage {
  job_id: string;
  message: string;
  progress: number;
  status?: Job['status'];
}

interface ReconnectState {
  nextRetryCount: number;
  shouldReconnect: boolean;
  status: WsStatus;
}

export function getConnectStatus(retryCount: number): WsStatus {
  return retryCount > 0 ? 'reconnecting' : 'connecting';
}

export function getReconnectState(retryCount: number, maxRetry = MAX_WEBSOCKET_RETRY): ReconnectState {
  const nextRetryCount = retryCount + 1;
  const shouldReconnect = nextRetryCount < maxRetry;

  return {
    nextRetryCount,
    shouldReconnect,
    status: shouldReconnect ? 'reconnecting' : 'disconnected',
  };
}

export function createProgressWebSocket(token: string | null, wsBase: string): WebSocket {
  const socketUrl = `${wsBase}/ws/progress`;

  return token
    ? new WebSocket(socketUrl, ['bearer', token])
    : new WebSocket(socketUrl);
}

export function parseProgressMessage(data: string): ProgressMessage | null {
  try {
    const parsed = JSON.parse(data) as Partial<ProgressMessage>;
    if (!parsed.job_id || typeof parsed.message !== 'string' || typeof parsed.progress !== 'number') {
      return null;
    }

    return {
      job_id: parsed.job_id,
      message: parsed.message,
      progress: parsed.progress,
      status: parsed.status,
    };
  } catch (error) {
    console.error('WebSocket message parse error:', error);
    return null;
  }
}
