import { create, type StateCreator } from 'zustand';

import { jobsApi } from '../api/client';
import { JOB_HISTORY_STORAGE_KEY } from '../auth/isolation';
import { useAuthRuntimeStore } from '../auth/runtime';
import { tSafe } from '../i18n';
import type { ClipReadyEntry, DownloadProgress, Job, JobStatus, JobTimelineEntry, JobTimelineSource, LogEntry, WsStatus } from '../types';
import { readStored } from '../utils/storage';

const MAX_CORE_LOG_ENTRIES = 300;
const INITIAL_WS_STATUS: WsStatus = 'disconnected';
const JOB_HISTORY_TTL_MS = 5 * 60 * 1000;

interface TimelineEventPayload {
    at: string;
    event_id: string;
    job_id: string;
    message: string;
    progress: number;
    source?: JobTimelineSource;
    status?: JobStatus;
    download_progress?: DownloadProgress;
}

interface RegisterQueuedJobPayload {
    job_id: string;
    message?: string;
    style?: string;
    url: string;
}

interface PersistedJobHistorySnapshot {
    version: 1;
    jobs: Job[];
    clipReadyByJob: Record<string, ClipReadyEntry[]>;
    jobHistoryExpiresAt: number | null;
    terminalHistoryCutoffAt: number;
}

interface HydratedJobHistoryState {
    clipReadyByJob: Record<string, ClipReadyEntry[]>;
    hasRetainedHistory: boolean;
    jobHistoryExpiresAt: number | null;
    jobs: Job[];
    terminalHistoryCutoffAt: number;
}

export interface JobState {
    jobs: Job[];
    clips: string[];
    wsStatus: WsStatus;
    lastError: string | null;
    clipReadySignal: number;
    clipReadyByJob: Record<string, ClipReadyEntry[]>;
    /** Job tamamlandığında artar; ClipGallery yenileme tetikler */
    refreshClipsTrigger: number;
    jobHistoryExpiresAt: number | null;
    hasRetainedHistory: boolean;
    fetchJobs: () => Promise<void>;
    requestClipsRefresh: () => void;
    registerQueuedJob: (payload: RegisterQueuedJobPayload) => void;
    mergeJobTimelineEvent: (event: TimelineEventPayload) => void;
    markClipReady: (payload: ClipReadyEntry) => void;
    cancelJob: (job_id: string) => Promise<void>;
    setWsStatus: (status: WsStatus) => void;
    addClip: (url: string) => void;
    clearError: () => void;
    clearRetainedHistory: () => void;
    reset: () => void;
}

type JobStoreSet = Parameters<StateCreator<JobState>>[0];
type JobStoreGet = Parameters<StateCreator<JobState>>[1];

let terminalHistoryCutoffAt = 0;
let jobHistoryExpiryTimeoutId: number | null = null;

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

function isActiveJobStatus(status: JobStatus): boolean {
    return status === 'queued' || status === 'processing';
}

function normalizeTimelineSource(source?: JobTimelineSource): JobTimelineSource {
    return source && ['api', 'worker', 'websocket', 'clip_ready'].includes(source) ? source : 'worker';
}

function normalizeDownloadProgress(downloadProgress?: DownloadProgress): DownloadProgress | undefined {
    if (!downloadProgress || downloadProgress.phase !== 'download') {
        return undefined;
    }

    const normalized: DownloadProgress = { phase: 'download' };
    for (const key of ['downloaded_bytes', 'total_bytes', 'total_bytes_estimate', 'percent'] as const) {
        const value = downloadProgress[key];
        if (typeof value === 'number' && Number.isFinite(value)) {
            normalized[key] = value;
        }
    }
    for (const key of ['speed_text', 'eta_text', 'status'] as const) {
        const value = downloadProgress[key];
        if (typeof value === 'string' && value) {
            normalized[key] = value;
        }
    }

    return Object.keys(normalized).length > 1 ? normalized : undefined;
}

function getDefaultQueuedMessage(): string {
    return tSafe('jobQueue.waitingForSlot', {
        defaultValue: 'Waiting for the next job slot.',
    });
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
        download_progress: normalizeDownloadProgress(entry.download_progress as DownloadProgress | undefined),
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

function resolveNormalizedProgress(job: Job, latestEvent?: JobTimelineEntry): number {
    return typeof job.progress === 'number'
        ? Math.max(0, job.progress)
        : Math.max(0, latestEvent?.progress ?? 0);
}

function resolveNormalizedStatus(job: Job, latestEvent?: JobTimelineEntry): JobStatus {
    return resolveJobStatus(
        typeof job.progress === 'number' ? job.progress : latestEvent?.progress ?? 0,
        job.status,
        latestEvent?.status ?? 'queued',
    );
}

function normalizeJob(job: Job): Job {
    const timeline = normalizeTimeline(job.job_id, job.timeline);
    const latestEvent = timeline[timeline.length - 1];
    const progress = resolveNormalizedProgress(job, latestEvent);
    const status = resolveNormalizedStatus(job, latestEvent);
    const downloadProgress = normalizeDownloadProgress(job.download_progress)
        ?? normalizeDownloadProgress(latestEvent?.download_progress);

    return {
        ...job,
        progress,
        status,
        last_message: job.last_message || latestEvent?.message || '',
        created_at: typeof job.created_at === 'number' ? job.created_at : Date.now() / 1000,
        download_progress: downloadProgress,
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
            download_progress: incomingJob.download_progress ?? existingJob.download_progress,
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

function buildQueuedTimelineEntry(job_id: string, message = getDefaultQueuedMessage()): JobTimelineEntry {
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

function hasActiveJobs(jobs: Job[]): boolean {
    return jobs.some((job) => isActiveJobStatus(job.status));
}

function parseTimestampMs(value?: string): number | null {
    if (!value) {
        return null;
    }
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
}

function resolveJobActivityAt(job: Job): number {
    const latestTimelineEntry = job.timeline?.[job.timeline.length - 1];
    const timelineAt = parseTimestampMs(latestTimelineEntry?.at);
    if (timelineAt !== null) {
        return timelineAt;
    }
    return Math.max(0, job.created_at * 1000);
}

function shouldKeepJobByCutoff(job: Job, cutoffAt: number): boolean {
    return isActiveJobStatus(job.status) || resolveJobActivityAt(job) >= cutoffAt;
}

function filterJobsForVisibility(
    jobs: Job[],
    { cutoffAt }: { cutoffAt: number },
): Job[] {
    const normalizedJobs = mergeJobs([], jobs).filter((job) => shouldKeepJobByCutoff(job, cutoffAt));
    return normalizedJobs;
}

function normalizeClipReadyEntry(entry: ClipReadyEntry): ClipReadyEntry | null {
    if (typeof entry.job_id !== 'string' || !entry.job_id || typeof entry.clipName !== 'string' || !entry.clipName) {
        return null;
    }
    if (typeof entry.message !== 'string' || typeof entry.progress !== 'number') {
        return null;
    }
    return {
        at: typeof entry.at === 'string' && entry.at ? entry.at : new Date().toISOString(),
        clipName: entry.clipName,
        job_id: entry.job_id,
        message: entry.message,
        progress: entry.progress,
        projectId: typeof entry.projectId === 'string' ? entry.projectId : undefined,
        uiTitle: typeof entry.uiTitle === 'string' ? entry.uiTitle : undefined,
    };
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

function filterClipReadyByJob(
    clipReadyByJob: Record<string, ClipReadyEntry[]>,
    jobs: Job[],
    cutoffAt: number,
): Record<string, ClipReadyEntry[]> {
    const visibleJobIds = new Set(jobs.map((job) => job.job_id));
    const filtered: Record<string, ClipReadyEntry[]> = {};

    for (const [jobId, entries] of Object.entries(clipReadyByJob)) {
        if (!visibleJobIds.has(jobId)) {
            continue;
        }

        const nextEntries = (entries ?? [])
            .map(normalizeClipReadyEntry)
            .filter((entry): entry is ClipReadyEntry => entry !== null)
            .filter((entry) => {
                const at = parseTimestampMs(entry.at);
                return at === null || at >= cutoffAt;
            })
            .sort((left, right) => {
                const byTime = left.at.localeCompare(right.at);
                return byTime !== 0 ? byTime : left.clipName.localeCompare(right.clipName);
            });

        if (nextEntries.length > 0) {
            filtered[jobId] = nextEntries;
        }
    }

    return filtered;
}

function reconcileFetchedJobs(existingJobs: Job[], incomingJobs: Job[]): Job[] {
    const retainedJobs = existingJobs.filter((job) => !isActiveJobStatus(job.status) && shouldKeepJobByCutoff(job, terminalHistoryCutoffAt));
    const filteredIncomingJobs = incomingJobs.filter((job) => shouldKeepJobByCutoff(job, terminalHistoryCutoffAt));
    return mergeJobs(retainedJobs, filteredIncomingJobs);
}

function resolveJobHistoryExpiresAt(
    previousJobs: Job[],
    nextJobs: Job[],
    previousExpiresAt: number | null,
    now: number,
): number | null {
    if (nextJobs.length === 0) {
        return null;
    }
    if (hasActiveJobs(nextJobs)) {
        return null;
    }
    if (hasActiveJobs(previousJobs) || previousExpiresAt === null || previousExpiresAt <= now) {
        return now + JOB_HISTORY_TTL_MS;
    }
    return previousExpiresAt;
}

function buildRetainedHistoryState(
    previousJobs: Job[],
    nextJobs: Job[],
    clipReadyByJob: Record<string, ClipReadyEntry[]>,
    previousExpiresAt: number | null,
    now: number,
): Pick<JobState, 'clipReadyByJob' | 'hasRetainedHistory' | 'jobHistoryExpiresAt' | 'jobs'> {
    const visibleJobs = filterJobsForVisibility(nextJobs, {
        cutoffAt: terminalHistoryCutoffAt,
    });
    const historyExpiresAt = resolveJobHistoryExpiresAt(previousJobs, visibleJobs, previousExpiresAt, now);
    return {
        jobs: visibleJobs,
        clipReadyByJob: filterClipReadyByJob(clipReadyByJob, visibleJobs, terminalHistoryCutoffAt),
        jobHistoryExpiresAt: historyExpiresAt,
        hasRetainedHistory: visibleJobs.length > 0,
    };
}

function readPersistedJobHistory(now = Date.now()): HydratedJobHistoryState {
    const snapshot = readStored<PersistedJobHistorySnapshot | null>(JOB_HISTORY_STORAGE_KEY, null);
    if (!snapshot || snapshot.version !== 1) {
        return {
            jobs: [],
            clipReadyByJob: {},
            jobHistoryExpiresAt: null,
            hasRetainedHistory: false,
            terminalHistoryCutoffAt: 0,
        };
    }

    const cutoffAt = typeof snapshot.terminalHistoryCutoffAt === 'number' && Number.isFinite(snapshot.terminalHistoryCutoffAt)
        ? Math.max(0, snapshot.terminalHistoryCutoffAt)
        : 0;
    const rawExpiresAt = typeof snapshot.jobHistoryExpiresAt === 'number' && Number.isFinite(snapshot.jobHistoryExpiresAt)
        ? snapshot.jobHistoryExpiresAt
        : null;
    const visibleJobs = rawExpiresAt !== null && rawExpiresAt <= now
        ? []
        : filterJobsForVisibility(snapshot.jobs ?? [], {
            cutoffAt,
        });
    const historyExpiresAt = resolveJobHistoryExpiresAt([], visibleJobs, rawExpiresAt, now);

    return {
        jobs: visibleJobs,
        clipReadyByJob: filterClipReadyByJob(snapshot.clipReadyByJob ?? {}, visibleJobs, cutoffAt),
        jobHistoryExpiresAt: historyExpiresAt,
        hasRetainedHistory: visibleJobs.length > 0,
        terminalHistoryCutoffAt: cutoffAt,
    };
}

function clearJobHistoryExpiryTimeout(): void {
    if (typeof window === 'undefined') {
        jobHistoryExpiryTimeoutId = null;
        return;
    }
    if (jobHistoryExpiryTimeoutId !== null) {
        window.clearTimeout(jobHistoryExpiryTimeoutId);
        jobHistoryExpiryTimeoutId = null;
    }
}

function persistJobHistorySnapshot(state: Pick<JobState, 'clipReadyByJob' | 'jobHistoryExpiresAt' | 'jobs'>): void {
    if (typeof window === 'undefined') {
        return;
    }

    if (state.jobs.length === 0 && Object.keys(state.clipReadyByJob).length === 0 && state.jobHistoryExpiresAt === null && terminalHistoryCutoffAt === 0) {
        window.localStorage.removeItem(JOB_HISTORY_STORAGE_KEY);
        return;
    }

    const snapshot: PersistedJobHistorySnapshot = {
        version: 1,
        jobs: state.jobs,
        clipReadyByJob: state.clipReadyByJob,
        jobHistoryExpiresAt: state.jobHistoryExpiresAt,
        terminalHistoryCutoffAt,
    };
    window.localStorage.setItem(JOB_HISTORY_STORAGE_KEY, JSON.stringify(snapshot));
}

function scheduleJobHistoryExpiry(set: JobStoreSet, get: JobStoreGet): void {
    if (typeof window === 'undefined') {
        return;
    }

    clearJobHistoryExpiryTimeout();
    const expiresAt = get().jobHistoryExpiresAt;
    if (expiresAt === null) {
        return;
    }

    jobHistoryExpiryTimeoutId = window.setTimeout(() => {
        const state = get();
        if (state.jobHistoryExpiresAt === null || state.jobHistoryExpiresAt > Date.now() || hasActiveJobs(state.jobs)) {
            scheduleJobHistoryExpiry(set, get);
            return;
        }

        terminalHistoryCutoffAt = Date.now();
        set({
            jobs: [],
            clipReadyByJob: {},
            jobHistoryExpiresAt: null,
            hasRetainedHistory: false,
        });
        persistJobHistorySnapshot({
            jobs: [],
            clipReadyByJob: {},
            jobHistoryExpiresAt: null,
        });
        clearJobHistoryExpiryTimeout();
    }, Math.max(0, expiresAt - Date.now()));
}

function syncPersistedJobHistory(set: JobStoreSet, get: JobStoreGet): void {
    persistJobHistorySnapshot({
        jobs: get().jobs,
        clipReadyByJob: get().clipReadyByJob,
        jobHistoryExpiresAt: get().jobHistoryExpiresAt,
    });
    scheduleJobHistoryExpiry(set, get);
}

function createFetchJobsAction(set: JobStoreSet, get: JobStoreGet) {
    return async () => {
        if (!useAuthRuntimeStore.getState().canUseProtectedRequests) {
            return;
        }

        try {
            const data = await jobsApi.list();
            set((state) => {
                const reconciledJobs = reconcileFetchedJobs(state.jobs, data.jobs);
                const retainedState = buildRetainedHistoryState(
                    state.jobs,
                    reconciledJobs,
                    state.clipReadyByJob,
                    state.jobHistoryExpiresAt,
                    Date.now(),
                );
                return {
                    jobs: retainedState.jobs,
                    clipReadyByJob: retainedState.clipReadyByJob,
                    jobHistoryExpiresAt: retainedState.jobHistoryExpiresAt,
                    hasRetainedHistory: retainedState.hasRetainedHistory,
                    lastError: null,
                    refreshClipsTrigger: state.refreshClipsTrigger + countNewlyCompletedJobs(state.jobs, retainedState.jobs),
                };
            });
            syncPersistedJobHistory(set, get);
        } catch (err) {
            const msg = err instanceof Error ? err.message : tSafe('jobQueue.errors.fetchFailed', { defaultValue: 'Job list could not be fetched.' });
            set({ lastError: msg });
            console.error('Failed to fetch jobs', err);
        }
    };
}

function createRegisterQueuedJobAction(set: JobStoreSet, get: JobStoreGet) {
    return ({ job_id, message = getDefaultQueuedMessage(), style = '', url }: RegisterQueuedJobPayload) => {
        set((state) => {
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
            const retainedState = buildRetainedHistoryState(
                state.jobs,
                nextJobs,
                state.clipReadyByJob,
                state.jobHistoryExpiresAt,
                Date.now(),
            );

            return {
                jobs: retainedState.jobs,
                clipReadyByJob: retainedState.clipReadyByJob,
                jobHistoryExpiresAt: retainedState.jobHistoryExpiresAt,
                hasRetainedHistory: retainedState.hasRetainedHistory,
                lastError: null,
            };
        });
        syncPersistedJobHistory(set, get);
    };
}

function createMergeJobTimelineEventAction(set: JobStoreSet, get: JobStoreGet) {
    return ({ at, event_id, job_id, message, progress, source, status, download_progress }: TimelineEventPayload) => {
        set((state) => {
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
                download_progress,
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
                        download_progress: normalizeDownloadProgress(download_progress) ?? existingJob?.download_progress,
                        timeline: mergeTimelines(existingJob?.timeline, [timelineEntry]),
                    }),
                ],
            );
            const retainedState = buildRetainedHistoryState(
                state.jobs,
                nextJobs,
                state.clipReadyByJob,
                state.jobHistoryExpiresAt,
                Date.now(),
            );
            const nextJob = retainedState.jobs.find((job) => job.job_id === job_id);
            const newlyCompleted = nextJob?.status === 'completed' && previousStatus !== 'completed' ? 1 : 0;

            return {
                jobs: retainedState.jobs,
                clipReadyByJob: retainedState.clipReadyByJob,
                jobHistoryExpiresAt: retainedState.jobHistoryExpiresAt,
                hasRetainedHistory: retainedState.hasRetainedHistory,
                refreshClipsTrigger: state.refreshClipsTrigger + newlyCompleted,
            };
        });
        syncPersistedJobHistory(set, get);
    };
}

function createCancelJobAction(set: JobStoreSet, get: JobStoreGet) {
    return async (job_id: string) => {
        try {
            await jobsApi.cancel(job_id);
            set((state) => {
                const nextJobs = state.jobs.map((job) => (
                    job.job_id === job_id
                        ? normalizeJob({ ...job, status: 'cancelled', progress: job.progress, last_message: tSafe('common.status.cancelled') })
                        : job
                ));
                const retainedState = buildRetainedHistoryState(
                    state.jobs,
                    nextJobs,
                    state.clipReadyByJob,
                    state.jobHistoryExpiresAt,
                    Date.now(),
                );
                return {
                    jobs: retainedState.jobs,
                    clipReadyByJob: retainedState.clipReadyByJob,
                    jobHistoryExpiresAt: retainedState.jobHistoryExpiresAt,
                    hasRetainedHistory: retainedState.hasRetainedHistory,
                    lastError: null,
                };
            });
            syncPersistedJobHistory(set, get);
        } catch (err) {
            const msg = err instanceof Error ? err.message : tSafe('jobQueue.errors.cancelFailed', { defaultValue: 'Cancel failed.' });
            set({ lastError: msg });
            console.error('Failed to cancel job', err);
        }
    };
}

const hydratedJobHistory = readPersistedJobHistory();
terminalHistoryCutoffAt = hydratedJobHistory.terminalHistoryCutoffAt;

function createJobStoreState(set: JobStoreSet, get: JobStoreGet): JobState {
    return {
        jobs: hydratedJobHistory.jobs,
        clips: [],
        wsStatus: INITIAL_WS_STATUS,
        lastError: null,
        clipReadySignal: 0,
        clipReadyByJob: hydratedJobHistory.clipReadyByJob,
        refreshClipsTrigger: 0,
        jobHistoryExpiresAt: hydratedJobHistory.jobHistoryExpiresAt,
        hasRetainedHistory: hydratedJobHistory.hasRetainedHistory,

        fetchJobs: createFetchJobsAction(set, get),

        clearError: () => set({ lastError: null }),

        requestClipsRefresh: () => set((state) => ({
            refreshClipsTrigger: state.refreshClipsTrigger + 1,
        })),

        registerQueuedJob: createRegisterQueuedJobAction(set, get),

        mergeJobTimelineEvent: createMergeJobTimelineEventAction(set, get),

        markClipReady: (payload) => {
            set((state) => {
                const normalizedPayload = normalizeClipReadyEntry(payload);
                if (!normalizedPayload) {
                    return state;
                }
                const nextClipReadyByJob = {
                    ...state.clipReadyByJob,
                    [normalizedPayload.job_id]: mergeClipReadyEntries(state.clipReadyByJob[normalizedPayload.job_id], normalizedPayload),
                };
                return {
                    clipReadySignal: state.clipReadySignal + 1,
                    clipReadyByJob: filterClipReadyByJob(nextClipReadyByJob, state.jobs, terminalHistoryCutoffAt),
                };
            });
            syncPersistedJobHistory(set, get);
        },

        cancelJob: createCancelJobAction(set, get),

        setWsStatus: (status) => set({ wsStatus: status }),
        addClip: (url) => set((state) => ({ clips: [...state.clips, url] })),
        clearRetainedHistory: () => {
            const state = get();
            if (hasActiveJobs(state.jobs)) {
                return;
            }

            terminalHistoryCutoffAt = Date.now();
            set({
                jobs: [],
                clipReadyByJob: {},
                jobHistoryExpiresAt: null,
                hasRetainedHistory: false,
            });
            syncPersistedJobHistory(set, get);
        },
        reset: () => {
            terminalHistoryCutoffAt = 0;
            clearJobHistoryExpiryTimeout();
            set({
                jobs: [],
                lastError: null,
                clipReadySignal: 0,
                clipReadyByJob: {},
                refreshClipsTrigger: 0,
                wsStatus: INITIAL_WS_STATUS,
                jobHistoryExpiresAt: null,
                hasRetainedHistory: false,
            });
            syncPersistedJobHistory(set, get);
        },
    };
}

export const useJobStore = create<JobState>((set, get) => createJobStoreState(set, get));

scheduleJobHistoryExpiry(useJobStore.setState, useJobStore.getState);
