import { useEffect, useRef } from 'react';
import { useJobStore } from '../store/useJobStore';
import { WS_BASE } from '../config';
import { getFreshToken } from '../api/client';

const MAX_RETRY = 5;
const RETRY_DELAY = 3000;

export const useWebSocket = (enabled = true) => {
    const ws = useRef<WebSocket | null>(null);
    const retryCount = useRef(0);
    const reconnectTimeoutId = useRef<number | null>(null);
    const isUnmounted = useRef(false);
    const { updateJobProgress, fetchJobs, setWsStatus } = useJobStore();

    const updateJobProgressRef = useRef(updateJobProgress);
    const fetchJobsRef = useRef(fetchJobs);
    const setWsStatusRef = useRef(setWsStatus);

    useEffect(() => {
        updateJobProgressRef.current = updateJobProgress;
    }, [updateJobProgress]);

    useEffect(() => {
        fetchJobsRef.current = fetchJobs;
    }, [fetchJobs]);

    useEffect(() => {
        setWsStatusRef.current = setWsStatus;
    }, [setWsStatus]);

    useEffect(() => {
        if (!enabled) {
            setWsStatusRef.current('disconnected');
            return;
        }
        isUnmounted.current = false;
        fetchJobsRef.current();

        const connect = async () => {
            if (retryCount.current >= MAX_RETRY) {
                setWsStatusRef.current('disconnected');
                return;
            }

            if (retryCount.current > 0) {
                setWsStatusRef.current('reconnecting');
            } else {
                setWsStatusRef.current('connecting');
            }

            const token = await getFreshToken();
            const socketUrl = `${WS_BASE}/ws/progress`;
            ws.current = token
                ? new WebSocket(socketUrl, ['bearer', token])
                : new WebSocket(socketUrl);

            ws.current.onopen = () => {
                retryCount.current = 0;
                setWsStatusRef.current('connected');
                void fetchJobsRef.current();
            };

            ws.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.job_id) {
                        updateJobProgressRef.current(
                            data.job_id,
                            data.message,
                            data.progress,
                            data.status,
                        );
                    }
                } catch (err) {
                    console.error('WebSocket message parse error:', err);
                }
            };

            ws.current.onerror = () => {
                /* onclose will fire after onerror */
            };

            ws.current.onclose = () => {
                if (isUnmounted.current) {
                    return;
                }

                retryCount.current += 1;
                if (retryCount.current < MAX_RETRY) {
                    setWsStatusRef.current('reconnecting');
                    reconnectTimeoutId.current = window.setTimeout(() => {
                        void connect();
                    }, RETRY_DELAY);
                } else {
                    setWsStatusRef.current('disconnected');
                }
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
    }, [enabled]);
};
