import { useEffect, useRef, type MutableRefObject } from 'react';

import { getFreshToken } from '../api/client';
import { useAuthRuntimeStore } from '../auth/runtime';
import { WS_BASE } from '../config';
import { useJobStore, type JobState } from '../store/useJobStore';
import {
  MAX_WEBSOCKET_RETRY,
  RETRY_DELAY_MS,
  createProgressWebSocket,
  getConnectStatus,
  getReconnectState,
  parseProgressMessage,
} from './useWebSocket.helpers';

function useLatestRef<T>(value: T) {
  const ref = useRef(value);

  useEffect(() => {
    ref.current = value;
  }, [value]);

  return ref;
}

function useWebSocketStoreRefs() {
  const mergeJobTimelineEvent = useJobStore((state) => state.mergeJobTimelineEvent);
  const markClipReady = useJobStore((state) => state.markClipReady);
  const fetchJobs = useJobStore((state) => state.fetchJobs);
  const setWsStatus = useJobStore((state) => state.setWsStatus);

  return {
    fetchJobsRef: useLatestRef(fetchJobs),
    markClipReadyRef: useLatestRef(markClipReady),
    mergeJobTimelineEventRef: useLatestRef(mergeJobTimelineEvent),
    setWsStatusRef: useLatestRef(setWsStatus),
  };
}

function hasFreshProtectedAuth() {
  const runtimeState = useAuthRuntimeStore.getState();
  return runtimeState.canUseProtectedRequests && runtimeState.backendAuthStatus === 'fresh';
}

function clearReconnectTimeout(reconnectTimeoutId: MutableRefObject<number | null>) {
  if (reconnectTimeoutId.current !== null) {
    clearTimeout(reconnectTimeoutId.current);
    reconnectTimeoutId.current = null;
  }
}

function closeSocket(
  ws: MutableRefObject<WebSocket | null>,
  reconnectTimeoutId: MutableRefObject<number | null>,
  isUnmounted: MutableRefObject<boolean>,
) {
  isUnmounted.current = true;

  if (ws.current) {
    ws.current.close();
    ws.current = null;
  }

  clearReconnectTimeout(reconnectTimeoutId);
}

function handleProgressEvent(
  eventData: string,
  mergeJobTimelineEvent: JobState['mergeJobTimelineEvent'],
  markClipReady: JobState['markClipReady'],
) {
  const progressMessage = parseProgressMessage(eventData);
  if (!progressMessage) {
    return;
  }

  mergeJobTimelineEvent({
    at: progressMessage.at,
    event_id: progressMessage.event_id,
    job_id: progressMessage.job_id,
    message: progressMessage.message,
    progress: progressMessage.progress,
    source: progressMessage.source,
    status: progressMessage.status,
    download_progress: progressMessage.download_progress,
  });

  if (progressMessage.event_type === 'clip_ready' && progressMessage.clip_name) {
    markClipReady({
      at: progressMessage.at,
      clipName: progressMessage.clip_name,
      job_id: progressMessage.job_id,
      message: progressMessage.message,
      progress: progressMessage.progress,
      projectId: progressMessage.project_id,
      uiTitle: progressMessage.ui_title,
    });
  }
}

function attachSocketHandlers({
  connect,
  fetchJobsRef,
  isUnmounted,
  markClipReadyRef,
  mergeJobTimelineEventRef,
  reconnectTimeoutId,
  retryCount,
  setWsStatusRef,
  ws,
}: {
  connect: () => Promise<void>;
  fetchJobsRef: MutableRefObject<JobState['fetchJobs']>;
  isUnmounted: MutableRefObject<boolean>;
  markClipReadyRef: MutableRefObject<JobState['markClipReady']>;
  mergeJobTimelineEventRef: MutableRefObject<JobState['mergeJobTimelineEvent']>;
  reconnectTimeoutId: MutableRefObject<number | null>;
  retryCount: MutableRefObject<number>;
  setWsStatusRef: MutableRefObject<JobState['setWsStatus']>;
  ws: MutableRefObject<WebSocket | null>;
}) {
  if (!ws.current) {
    return;
  }

  ws.current.onopen = () => {
    retryCount.current = 0;
    setWsStatusRef.current('connected');
    void fetchJobsRef.current();
  };

  ws.current.onmessage = (event) => {
    handleProgressEvent(event.data, mergeJobTimelineEventRef.current, markClipReadyRef.current);
  };

  ws.current.onerror = () => {
    /* onclose will fire after onerror */
  };

  ws.current.onclose = () => {
    if (isUnmounted.current || !hasFreshProtectedAuth()) {
      setWsStatusRef.current('disconnected');
      return;
    }

    const reconnectState = getReconnectState(retryCount.current, MAX_WEBSOCKET_RETRY);
    retryCount.current = reconnectState.nextRetryCount;
    if (!reconnectState.shouldReconnect) {
      setWsStatusRef.current('disconnected');
      return;
    }

    setWsStatusRef.current(reconnectState.status);
    reconnectTimeoutId.current = window.setTimeout(() => {
      if (!hasFreshProtectedAuth()) {
        setWsStatusRef.current('disconnected');
        return;
      }
      void connect();
    }, RETRY_DELAY_MS);
  };
}

export const useWebSocket = (enabled = true) => {
  const ws = useRef<WebSocket | null>(null);
  const retryCount = useRef(0);
  const reconnectTimeoutId = useRef<number | null>(null);
  const isUnmounted = useRef(false);
  const backendAuthStatus = useAuthRuntimeStore((state) => state.backendAuthStatus);
  const canUseProtectedRequests = useAuthRuntimeStore((state) => state.canUseProtectedRequests);
  const { fetchJobsRef, markClipReadyRef, mergeJobTimelineEventRef, setWsStatusRef } = useWebSocketStoreRefs();
  const canConnect = enabled && canUseProtectedRequests && backendAuthStatus === 'fresh';

  useEffect(() => {
    if (!canConnect) {
      setWsStatusRef.current('disconnected');
      return;
    }

    isUnmounted.current = false;
    void fetchJobsRef.current();

    const connect = async () => {
      if (retryCount.current >= MAX_WEBSOCKET_RETRY) {
        setWsStatusRef.current('disconnected');
        return;
      }

      try {
        setWsStatusRef.current(getConnectStatus(retryCount.current));
        const token = await getFreshToken();
        if (isUnmounted.current) {
          return;
        }
        ws.current = createProgressWebSocket(token, WS_BASE);
      } catch {
        setWsStatusRef.current('disconnected');
        return;
      }

      attachSocketHandlers({
        connect,
        fetchJobsRef,
        isUnmounted,
        markClipReadyRef,
        mergeJobTimelineEventRef,
        reconnectTimeoutId,
        retryCount,
        setWsStatusRef,
        ws,
      });
    };

    void connect();

    return () => closeSocket(ws, reconnectTimeoutId, isUnmounted);
  }, [
    canConnect,
    fetchJobsRef,
    markClipReadyRef,
    mergeJobTimelineEventRef,
    setWsStatusRef,
  ]);
};
