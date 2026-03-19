import { create } from 'zustand';
import { useAuthRuntimeStore } from '../auth/runtime';
import type { Job, LogEntry, WsStatus } from '../types';
import { jobsApi } from '../api/client';

const MAX_CORE_LOG_ENTRIES = 300;

interface JobState {
    jobs: Job[];
    logs: LogEntry[];
    clips: string[];
    wsStatus: WsStatus;
    lastError: string | null;
    clipReadySignal: number;
    /** Job tamamlandığında artar; ClipGallery yenileme tetikler */
    refreshClipsTrigger: number;
    fetchJobs: () => Promise<void>;
    updateJobProgress: (job_id: string, msg: string, progress: number, status?: Job['status']) => void;
    markClipReady: (payload: { clipName: string; job_id: string; message: string; progress: number; projectId?: string; uiTitle?: string }) => void;
    cancelJob: (job_id: string) => Promise<void>;
    setWsStatus: (status: WsStatus) => void;
    addClip: (url: string) => void;
    clearError: () => void;
    reset: () => void;
}

export const useJobStore = create<JobState>((set) => ({
    jobs: [],
    logs: [],
    clips: [],
    wsStatus: 'connecting' as WsStatus,
    lastError: null,
    clipReadySignal: 0,
    refreshClipsTrigger: 0,

    fetchJobs: async () => {
        if (!useAuthRuntimeStore.getState().canUseProtectedRequests) {
            return;
        }

        try {
            const data = await jobsApi.list();
            set({ jobs: data.jobs, lastError: null });
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Job listesi alınamadı';
            set({ lastError: msg });
            console.error('Failed to fetch jobs', err);
        }
    },

    clearError: () => set({ lastError: null }),

    updateJobProgress: (job_id: string, msg: string, progress: number, status?: Job['status']) => set((state) => {
        const jobExists = state.jobs.some(j => j.job_id === job_id);
        const nextStatus: Job['status'] = status
            ?? (progress < 0 ? 'error' : progress < 100 ? 'processing' : 'completed');
        const nextProgress = progress < 0 ? 0 : progress;
        const jobCompleted = progress >= 100 && nextStatus !== 'empty';
        const fallbackJob: Job = {
            job_id,
            url: '',
            style: '',
            status: nextStatus,
            progress: nextProgress,
            last_message: msg,
            created_at: Date.now() / 1000,
        };
        const updatedJobs = state.jobs.map((job): Job =>
            job.job_id === job_id
                ? { ...job, status: nextStatus, progress: nextProgress, last_message: msg }
                : job
        );

        return {
            jobs: jobExists ? updatedJobs : [fallbackJob, ...state.jobs],
            logs: [
                ...state.logs,
                { message: `[${job_id}] ${msg}`, progress, timestamp: new Date().toLocaleTimeString() },
            ].slice(-MAX_CORE_LOG_ENTRIES),
            refreshClipsTrigger: jobCompleted ? state.refreshClipsTrigger + 1 : state.refreshClipsTrigger,
        };
    }),

    markClipReady: ({ clipName, job_id, message, progress, projectId, uiTitle }) => set((state) => ({
        clipReadySignal: state.clipReadySignal + 1,
        logs: [
            ...state.logs,
            {
                message: `[${job_id}] ${message}${uiTitle ? ` (${uiTitle})` : ''} -> ${projectId ?? 'unknown'}/${clipName}`,
                progress,
                timestamp: new Date().toLocaleTimeString(),
            },
        ].slice(-MAX_CORE_LOG_ENTRIES),
    })),

    cancelJob: async (job_id) => {
        try {
            await jobsApi.cancel(job_id);
            set((state) => ({
                jobs: state.jobs.map(j => j.job_id === job_id ? { ...j, status: 'cancelled' } : j),
                lastError: null,
            }));
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'İptal başarısız';
            set({ lastError: msg });
            console.error('Failed to cancel job', err);
        }
    },

    setWsStatus: (status) => set({ wsStatus: status }),
    addClip: (url) => set((state) => ({ clips: [...state.clips, url] })),
    reset: () => set({ jobs: [], logs: [], lastError: null, clipReadySignal: 0, refreshClipsTrigger: 0, wsStatus: 'connecting' }),
}));
