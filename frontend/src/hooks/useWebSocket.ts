import { useEffect, useRef } from 'react';
import { useJobStore } from '../store/useJobStore';
import { WS_BASE } from '../config';

const MAX_RETRY = 5;
const RETRY_DELAY = 3000;

export const useWebSocket = () => {
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
        isUnmounted.current = false;
        fetchJobsRef.current();

        const connect = () => {
            if (retryCount.current >= MAX_RETRY) {
                setWsStatusRef.current('disconnected');
                return;
            }

            if (retryCount.current > 0) {
                setWsStatusRef.current('reconnecting');
            } else {
                setWsStatusRef.current('connecting');
            }

            ws.current = new WebSocket(`${WS_BASE}/ws/progress`);

            ws.current.onopen = () => {
                retryCount.current = 0;
                setWsStatusRef.current('connected');
            };

            ws.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.job_id) {
                        updateJobProgressRef.current(data.job_id, data.message, data.progress);
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
                    reconnectTimeoutId.current = window.setTimeout(connect, RETRY_DELAY);
                } else {
                    setWsStatusRef.current('disconnected');
                }
            };
        };

        connect();

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
    }, []);
};
