import { create } from 'zustand';

import { jobsApi } from '../api/client';
import { useAuthRuntimeStore } from '../auth/runtime';
import type { ClipReadyEntry, Job, JobStatus, JobTimelineEntry, JobTimelineSource, LogEntry, WsStatus } from '../types';

const MAX_CORE_LOG_ENTRIES = 300;
const INITIAL_WS_STATUS: WsStatus = 'disconnected';
const DEFAULT_QUEUED_MESSAGE = 'İşlem kuyruğa alındı. GPU müsait olduğunda başlayacak.';

interface TimelineEventPayload {
    at: string;
    event_id: string;
    job_id: string;
    message: string;
    progress: number;
    source?: JobTimelineSource;
    status?: JobStatus;
}

interface RegisterQueuedJobPayload {
    job_id: string;
    message?: string;
    style?: string;
    url: string;
}

interface JobState {
    jobs: Job[];
    clips: string[];
    wsStatus: WsStatus;
    lastError: string | null;
    clipReadySignal: number;
    clipReadyByJob: Record<string, ClipReadyEntry[]>;
    /** Job tamamlandığında artar; ClipGallery yenileme tetikler */
    refreshClipsTrigger: number;
    fetchJobs: () => Promise<void>;
    registerQueuedJob: (payload: RegisterQueuedJobPayload) => void;
    mergeJobTimelineEvent: (event: TimelineEventPayload) => void;
    markClipReady: (payload: ClipReadyEntry) => void;
    cancelJob: (job_id: string) => Promise<void>;
    setWsStatus: (status: WsStatus) => void;
    addClip: (url: string) => void;
    clearError: () => void;
    reset: () => void;
}

function resolveJobStatus(progress: number, status?: JobStatus, currentStatus: JobStatus = 'queued'): JobStatus {
    if (status) {
        return status;
    }
    if (progress < 0) {
        return 'error';
    }
    if (progress >= 100) {
        return currentStatus === 'empty' || currentStatus === 'cancelled' ? currentStatus : 'completed';
    }
    if (currentStatus === 'queued' || currentStatus === 'processing') {
        return currentStatus;
    }
    return 'processing';
}

function normalizeTimelineSource(source?: JobTimelineSource): JobTimelineSource {
    return source && ['api', 'worker', 'websocket', 'clip_ready'].includes(source) ? source : 'worker';
}

function normalizeTimelineEntry(jobId: string, entry: Partial<JobTimelineEntry>): JobTimelineEntry | null {
    if (typeof entry.id !== 'string' || !entry.id) {
        return null;
    }
    if (typeof entry.message !== 'string') {
        return null;
    }
    if (typeof entry.progress !== 'number') {
        return null;
    }
    return {
        id: entry.id,
        at: typeof entry.at === 'string' && entry.at ? entry.at : new Date().toISOString(),
        job_id: typeof entry.job_id === 'string' && entry.job_id ? entry.job_id : jobId,
        status: resolveJobStatus(entry.progress, entry.status as JobStatus | undefined),
        progress: entry.progress,
        message: entry.message,
        source: normalizeTimelineSource(entry.source as JobTimelineSource | undefined),
    };
}

function mergeTimelines(
    existing: JobTimelineEntry[] | undefined,
    incoming: JobTimelineEntry[] | undefined,
): JobTimelineEntry[] {
    const merged = new Map<string, JobTimelineEntry>();

    for (const entry of existing ?? []) {
        merged.set(entry.id, entry);
    }
    for (const entry of incoming ?? []) {
        merged.set(entry.id, entry);
    }

    return Array.from(merged.values())
        .sort((left, right) => {
            const atComparison = left.at.localeCompare(right.at);
            return atComparison !== 0 ? atComparison : left.id.localeCompare(right.id);
        })
        .slice(-MAX_CORE_LOG_ENTRIES);
}

function normalizeTimeline(jobId: string, timeline: JobTimelineEntry[] | undefined): JobTimelineEntry[] {
    const normalizedEntries: JobTimelineEntry[] = [];
    for (const entry of timeline ?? []) {
        const normalizedEntry = normalizeTimelineEntry(jobId, entry);
        if (normalizedEntry) {
            normalizedEntries.push(normalizedEntry);
        }
    }
    return mergeTimelines([], normalizedEntries);
}

function normalizeJob(job: Job): Job {
    const timeline = normalizeTimeline(job.job_id, job.timeline);
    const latestEvent = timeline[timeline.length - 1];
    const progress = typeof job.progress === 'number'
        ? Math.max(0, job.progress)
        : Math.max(0, latestEvent?.progress ?? 0);
    const status = resolveJobStatus(
        typeof job.progress === 'number' ? job.progress : latestEvent?.progress ?? 0,
        job.status,
        latestEvent?.status ?? 'queued',
    );

    return {
        ...job,
        progress,
        status,
        last_message: job.last_message || latestEvent?.message || '',
        created_at: typeof job.created_at === 'number' ? job.created_at : Date.now() / 1000,
        timeline,
    };
}

function sortJobs(jobs: Job[]): Job[] {
    return [...jobs].sort((left, right) => right.created_at - left.created_at);
}

function mergeJobs(existingJobs: Job[], incomingJobs: Job[]): Job[] {
    const mergedJobs = new Map(existingJobs.map((job) => [job.job_id, normalizeJob(job)]));

    for (const incomingJob of incomingJobs.map(normalizeJob)) {
        const existingJob = mergedJobs.get(incomingJob.job_id);
        if (!existingJob) {
            mergedJobs.set(incomingJob.job_id, incomingJob);
            continue;
        }

        mergedJobs.set(incomingJob.job_id, normalizeJob({
            ...existingJob,
            ...incomingJob,
            url: incomingJob.url || existingJob.url,
            style: incomingJob.style || existingJob.style,
            last_message: incomingJob.last_message || existingJob.last_message,
            error: incomingJob.error ?? existingJob.error,
            timeline: mergeTimelines(existingJob.timeline, incomingJob.timeline),
        }));
    }

    return sortJobs(Array.from(mergedJobs.values()));
}

function countNewlyCompletedJobs(previousJobs: Job[], nextJobs: Job[]): number {
    const previousStatusById = new Map(previousJobs.map((job) => [job.job_id, job.status]));
    return nextJobs.reduce((count, job) => {
        if (job.status !== 'completed') {
            return count;
        }
        return previousStatusById.get(job.job_id) === 'completed' ? count : count + 1;
    }, 0);
}

function buildQueuedTimelineEntry(job_id: string, message = DEFAULT_QUEUED_MESSAGE): JobTimelineEntry {
    return {
        id: `${job_id}:queued`,
        at: new Date().toISOString(),
        job_id,
        status: 'queued',
        progress: 0,
        message,
        source: 'api',
    };
}

function buildLogTimestamp(at: string): string {
    const parsed = new Date(at);
    if (Number.isNaN(parsed.getTime())) {
        return at;
    }
    return parsed.toLocaleTimeString();
}

export function getFlattenedJobLogs(jobs: Job[]): LogEntry[] {
    return mergeJobs([], jobs)
        .flatMap((job) => job.timeline ?? [])
        .sort((left, right) => {
            const atComparison = left.at.localeCompare(right.at);
            return atComparison !== 0 ? atComparison : left.id.localeCompare(right.id);
        })
        .slice(-MAX_CORE_LOG_ENTRIES)
        .map((entry) => ({
            ...entry,
            timestamp: buildLogTimestamp(entry.at),
        }));
}

function buildFallbackJob(job_id: string, message: string, progress: number, status?: JobStatus): Job {
    const resolvedStatus = resolveJobStatus(progress, status);
    return normalizeJob({
        job_id,
        url: '',
        style: '',
        status: resolvedStatus,
        progress: Math.max(0, progress),
        last_message: message,
        created_at: Date.now() / 1000,
        timeline: [],
    });
}

function mergeClipReadyEntries(
    existing: ClipReadyEntry[] | undefined,
    incoming: ClipReadyEntry,
): ClipReadyEntry[] {
    const deduped = new Map<string, ClipReadyEntry>();

    for (const entry of existing ?? []) {
        deduped.set(`${entry.job_id}:${entry.projectId ?? ''}:${entry.clipName}:${entry.at}`, entry);
    }

    deduped.set(
        `${incoming.job_id}:${incoming.projectId ?? ''}:${incoming.clipName}:${incoming.at}`,
        incoming,
    );

    return Array.from(deduped.values()).sort((left, right) => {
        const byTime = left.at.localeCompare(right.at);
        return byTime !== 0 ? byTime : left.clipName.localeCompare(right.clipName);
    });
}

export const useJobStore = create<JobState>((set) => ({
    jobs: [],
    clips: [],
    wsStatus: INITIAL_WS_STATUS,
    lastError: null,
    clipReadySignal: 0,
    clipReadyByJob: {},
    refreshClipsTrigger: 0,

    fetchJobs: async () => {
        if (!useAuthRuntimeStore.getState().canUseProtectedRequests) {
            return;
        }

        try {
            const data = await jobsApi.list();
            set((state) => {
                const nextJobs = mergeJobs(state.jobs, data.jobs);
                return {
                    jobs: nextJobs,
                    lastError: null,
                    refreshClipsTrigger: state.refreshClipsTrigger + countNewlyCompletedJobs(state.jobs, nextJobs),
                };
            });
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Job listesi alınamadı';
            set({ lastError: msg });
            console.error('Failed to fetch jobs', err);
        }
    },

    clearError: () => set({ lastError: null }),

    registerQueuedJob: ({ job_id, message = DEFAULT_QUEUED_MESSAGE, style = '', url }) => set((state) => {
        const queuedEvent = buildQueuedTimelineEntry(job_id, message);
        const existingJob = state.jobs.find((job) => job.job_id === job_id);
        const nextJobs = mergeJobs(
            state.jobs.filter((job) => job.job_id !== job_id),
            [
                normalizeJob({
                    ...(existingJob ?? buildFallbackJob(job_id, message, 0, 'queued')),
                    job_id,
                    url,
                    style: existingJob?.style || style,
                    status: 'queued',
                    progress: 0,
                    last_message: message,
                    timeline: mergeTimelines(existingJob?.timeline, [queuedEvent]),
                }),
            ],
        );

        return {
            jobs: nextJobs,
            lastError: null,
        };
    }),

    mergeJobTimelineEvent: ({ at, event_id, job_id, message, progress, source, status }) => set((state) => {
        const existingJob = state.jobs.find((job) => job.job_id === job_id);
        const previousStatus = existingJob?.status;
        const timelineEntry = normalizeTimelineEntry(job_id, {
            id: event_id,
            at,
            job_id,
            message,
            progress,
            source: source ?? 'worker',
            status,
        });
        if (!timelineEntry) {
            return state;
        }

        const nextStatus = resolveJobStatus(progress, status, existingJob?.status ?? 'queued');
        const nextJobs = mergeJobs(
            state.jobs.filter((job) => job.job_id !== job_id),
            [
                normalizeJob({
                    ...(existingJob ?? buildFallbackJob(job_id, message, progress, nextStatus)),
                    status: nextStatus,
                    progress: Math.max(0, progress),
                    last_message: message,
                    timeline: mergeTimelines(existingJob?.timeline, [timelineEntry]),
                }),
            ],
        );
        const nextJob = nextJobs.find((job) => job.job_id === job_id);
        const newlyCompleted = nextJob?.status === 'completed' && previousStatus !== 'completed' ? 1 : 0;

        return {
            jobs: nextJobs,
            refreshClipsTrigger: state.refreshClipsTrigger + newlyCompleted,
        };
    }),

    markClipReady: (payload) => set((state) => ({
        clipReadySignal: state.clipReadySignal + 1,
        clipReadyByJob: {
            ...state.clipReadyByJob,
            [payload.job_id]: mergeClipReadyEntries(state.clipReadyByJob[payload.job_id], payload),
        },
    })),

    cancelJob: async (job_id) => {
        try {
            await jobsApi.cancel(job_id);
            set((state) => ({
                jobs: state.jobs.map((job) => (
                    job.job_id === job_id
                        ? normalizeJob({ ...job, status: 'cancelled', progress: job.progress, last_message: 'İş iptal edildi.' })
                        : job
                )),
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
    reset: () => set({
        jobs: [],
        lastError: null,
        clipReadySignal: 0,
        clipReadyByJob: {},
        refreshClipsTrigger: 0,
        wsStatus: INITIAL_WS_STATUS,
    }),
}));
