import type { DownloadProgress, Job, JobTimelineSource, WsStatus } from '../types';

export const MAX_WEBSOCKET_RETRY = 60;
export const RETRY_DELAY_MS = 3000;

interface WsParseTelemetry {
  parsed: number;
  dropped: number;
  droppedMissingJobId: number;
  droppedInvalidSchema: number;
  parseErrors: number;
}

interface ProgressMessage {
  event_type: 'progress' | 'clip_ready';
  event_id: string;
  at: string;
  job_id: string;
  message: string;
  progress: number;
  status?: Job['status'];
  source?: JobTimelineSource;
  download_progress?: DownloadProgress;
  project_id?: string;
  clip_name?: string;
  ui_title?: string;
}

interface ReconnectState {
  nextRetryCount: number;
  shouldReconnect: boolean;
  status: WsStatus;
}

const wsParseTelemetry: WsParseTelemetry = {
  parsed: 0,
  dropped: 0,
  droppedMissingJobId: 0,
  droppedInvalidSchema: 0,
  parseErrors: 0,
};

function recordDrop(kind: 'missing_job_id' | 'invalid_schema' | 'parse_error') {
  wsParseTelemetry.dropped += 1;
  if (kind === 'missing_job_id') {
    wsParseTelemetry.droppedMissingJobId += 1;
    return;
  }
  if (kind === 'invalid_schema') {
    wsParseTelemetry.droppedInvalidSchema += 1;
    return;
  }
  wsParseTelemetry.parseErrors += 1;
}

export function getWsParseTelemetrySnapshot(): WsParseTelemetry {
  return { ...wsParseTelemetry };
}

export function resetWsParseTelemetry(): void {
  wsParseTelemetry.parsed = 0;
  wsParseTelemetry.dropped = 0;
  wsParseTelemetry.droppedMissingJobId = 0;
  wsParseTelemetry.droppedInvalidSchema = 0;
  wsParseTelemetry.parseErrors = 0;
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

function parseProgressPayload(data: string): Partial<ProgressMessage> | null {
  try {
    return JSON.parse(data) as Partial<ProgressMessage>;
  } catch (error) {
    recordDrop('parse_error');
    console.error('WebSocket message parse error:', error);
    return null;
  }
}

function hasValidProgressShape(parsed: Partial<ProgressMessage>): parsed is Partial<ProgressMessage> & {
  job_id: string;
  message: string;
  progress: number;
} {
  if (!parsed.job_id) {
    recordDrop('missing_job_id');
    return false;
  }

  if (typeof parsed.message !== 'string' || typeof parsed.progress !== 'number') {
    recordDrop('invalid_schema');
    return false;
  }

  return true;
}

function resolveProgressEventId(parsed: Partial<ProgressMessage> & { job_id: string; progress: number }) {
  if (typeof parsed.event_id === 'string' && parsed.event_id) {
    return parsed.event_id;
  }

  return `${parsed.job_id}:${parsed.progress}:${Date.now()}`;
}

function resolveProgressSource(parsed: Partial<ProgressMessage>): JobTimelineSource {
  if (
    parsed.source === 'api'
    || parsed.source === 'worker'
    || parsed.source === 'websocket'
    || parsed.source === 'clip_ready'
  ) {
    return parsed.source;
  }

  return parsed.event_type === 'clip_ready' ? 'clip_ready' : 'worker';
}

function normalizeDownloadProgress(parsed: Partial<ProgressMessage>): DownloadProgress | undefined {
  const candidate = parsed.download_progress;
  if (!candidate || typeof candidate !== 'object') {
    return undefined;
  }

  const normalized: DownloadProgress = { phase: 'download' };

  for (const key of ['downloaded_bytes', 'total_bytes', 'total_bytes_estimate'] as const) {
    const value = candidate[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      normalized[key] = value;
    }
  }

  if (typeof candidate.percent === 'number' && Number.isFinite(candidate.percent)) {
    normalized.percent = candidate.percent;
  }

  for (const key of ['speed_text', 'eta_text', 'status'] as const) {
    const value = candidate[key];
    if (typeof value === 'string' && value) {
      normalized[key] = value;
    }
  }

  return Object.keys(normalized).length > 1 ? normalized : undefined;
}

export function parseProgressMessage(data: string): ProgressMessage | null {
  const parsed = parseProgressPayload(data);
  if (!parsed || !hasValidProgressShape(parsed)) {
    return null;
  }

  wsParseTelemetry.parsed += 1;
  return {
    event_type: parsed.event_type === 'clip_ready' ? 'clip_ready' : 'progress',
    event_id: resolveProgressEventId(parsed),
    at: typeof parsed.at === 'string' && parsed.at ? parsed.at : new Date().toISOString(),
    job_id: parsed.job_id,
    message: parsed.message,
    progress: parsed.progress,
    status: parsed.status,
    source: resolveProgressSource(parsed),
    download_progress: normalizeDownloadProgress(parsed),
    project_id: typeof parsed.project_id === 'string' ? parsed.project_id : undefined,
    clip_name: typeof parsed.clip_name === 'string' ? parsed.clip_name : undefined,
    ui_title: typeof parsed.ui_title === 'string' ? parsed.ui_title : undefined,
  };
}
