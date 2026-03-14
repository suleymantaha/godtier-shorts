import { useEffect, useRef } from 'react';

import { getFreshToken } from '../api/client';
import { WS_BASE } from '../config';
import { useJobStore } from '../store/useJobStore';
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

export const useWebSocket = (enabled = true) => {
  const ws = useRef<WebSocket | null>(null);
  const retryCount = useRef(0);
  const reconnectTimeoutId = useRef<number | null>(null);
  const isUnmounted = useRef(false);
  const { updateJobProgress, fetchJobs, setWsStatus } = useJobStore();
  const updateJobProgressRef = useLatestRef(updateJobProgress);
  const fetchJobsRef = useLatestRef(fetchJobs);
  const setWsStatusRef = useLatestRef(setWsStatus);

  useEffect(() => {
    if (!enabled) {
      setWsStatusRef.current('disconnected');
      return;
    }

    isUnmounted.current = false;

    const connect = async () => {
      if (retryCount.current >= MAX_WEBSOCKET_RETRY) {
        setWsStatusRef.current('disconnected');
        return;
      }

      setWsStatusRef.current(getConnectStatus(retryCount.current));
      ws.current = createProgressWebSocket(await getFreshToken(), WS_BASE);

      ws.current.onopen = () => {
        retryCount.current = 0;
        setWsStatusRef.current('connected');
        void fetchJobsRef.current();
      };

      ws.current.onmessage = (event) => {
        const progressMessage = parseProgressMessage(event.data);
        if (!progressMessage) {
          return;
        }

        updateJobProgressRef.current(
          progressMessage.job_id,
          progressMessage.message,
          progressMessage.progress,
          progressMessage.status,
        );
      };

      ws.current.onerror = () => {
        /* onclose will fire after onerror */
      };

      ws.current.onclose = () => {
        if (isUnmounted.current) {
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
          void connect();
        }, RETRY_DELAY_MS);
      };
    };

    void connect();

    return () => {
      isUnmounted.current = true;

      if (ws.current) {
        ws.current.close();
        ws.current = null;
      }

      if (reconnectTimeoutId.current !== null) {
        clearTimeout(reconnectTimeoutId.current);
        reconnectTimeoutId.current = null;
      }
    };
  }, [enabled, fetchJobsRef, setWsStatusRef, updateJobProgressRef]);
};
