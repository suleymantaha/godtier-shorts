import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { JOB_HISTORY_STORAGE_KEY } from '../../auth/isolation';

const listMock = vi.fn();
const cancelMock = vi.fn();
const authRuntimeState = {
  canUseProtectedRequests: true,
};

vi.mock('../../api/client', () => ({
  jobsApi: {
    cancel: (...args: unknown[]) => cancelMock(...args),
    list: (...args: unknown[]) => listMock(...args),
  },
}));

vi.mock('../../auth/runtime', () => ({
  useAuthRuntimeStore: {
    getState: () => authRuntimeState,
  },
}));

import { getFlattenedJobLogs, useJobStore } from '../../store/useJobStore';

function buildCompletedJob(overrides: Record<string, unknown> = {}) {
  const at = typeof overrides.at === 'string' ? overrides.at : '2026-03-20T00:00:04.000Z';
  return {
    job_id: 'job-completed',
    url: 'https://youtube.com/watch?v=done',
    style: 'TIKTOK',
    status: 'completed' as const,
    progress: 100,
    last_message: 'done',
    created_at: 2,
    timeline: [
      {
        id: 'evt-completed',
        at,
        job_id: 'job-completed',
        message: 'done',
        progress: 100,
        source: 'worker' as const,
        status: 'completed' as const,
      },
    ],
    ...overrides,
  };
}

async function loadFreshJobStoreModule() {
  vi.resetModules();
  return import('../../store/useJobStore');
}

describe('useJobStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    localStorage.clear();
    authRuntimeState.canUseProtectedRequests = true;
    useJobStore.getState().reset();
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  it('registers an optimistic queued log immediately', () => {
    useJobStore.getState().registerQueuedJob({
      job_id: 'job-1',
      message: 'queued now',
      style: 'TIKTOK',
      url: 'https://youtube.com/watch?v=test123',
    });

    const state = useJobStore.getState();
    const logs = getFlattenedJobLogs(state.jobs);

    expect(state.jobs[0]?.status).toBe('queued');
    expect(state.hasRetainedHistory).toBe(true);
    expect(logs).toHaveLength(1);
    expect(logs[0]).toMatchObject({
      id: 'job-1:queued',
      job_id: 'job-1',
      message: 'queued now',
      status: 'queued',
    });
  });

  it('hydrates retained jobs from local storage before any fetch runs', async () => {
    localStorage.setItem(JOB_HISTORY_STORAGE_KEY, JSON.stringify({
      version: 1,
      jobs: [
        buildCompletedJob(),
      ],
      clipReadyByJob: {
        'job-completed': [
          {
            at: '2026-03-20T00:00:04.000Z',
            clipName: 'clip-1.mp4',
            job_id: 'job-completed',
            message: 'done',
            progress: 100,
            projectId: 'proj-1',
            uiTitle: 'Hook',
          },
        ],
      },
      jobHistoryExpiresAt: Date.now() + 60_000,
      terminalHistoryCutoffAt: 0,
    }));

    const freshModule = await loadFreshJobStoreModule();
    const freshState = freshModule.useJobStore.getState();

    expect(freshState.jobs).toHaveLength(1);
    expect(freshState.hasRetainedHistory).toBe(true);
    expect(freshState.clipReadyByJob['job-completed']).toHaveLength(1);
  });
});

describe('useJobStore timeline merging', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    localStorage.clear();
    authRuntimeState.canUseProtectedRequests = true;
    useJobStore.getState().reset();
  });

  it('deduplicates timeline events shared by websocket and api hydration', async () => {
    useJobStore.getState().registerQueuedJob({
      job_id: 'job-1',
      message: 'queued now',
      style: 'TIKTOK',
      url: 'https://youtube.com/watch?v=test123',
    });

    useJobStore.getState().mergeJobTimelineEvent({
      at: '2026-03-20T00:00:01.000Z',
      event_id: 'evt-1',
      job_id: 'job-1',
      message: 'processing step',
      progress: 25,
      source: 'worker',
      status: 'processing',
    });

    listMock.mockResolvedValueOnce({
      jobs: [
        {
          job_id: 'job-1',
          url: 'https://youtube.com/watch?v=test123',
          style: 'TIKTOK',
          status: 'processing',
          progress: 25,
          last_message: 'processing step',
          created_at: 1,
          timeline: [
            {
              id: 'job-1:queued',
              at: '2026-03-20T00:00:00.000Z',
              job_id: 'job-1',
              message: 'queued now',
              progress: 0,
              source: 'api',
              status: 'queued',
            },
            {
              id: 'evt-1',
              at: '2026-03-20T00:00:01.000Z',
              job_id: 'job-1',
              message: 'processing step',
              progress: 25,
              source: 'worker',
              status: 'processing',
            },
          ],
        },
      ],
    });

    await useJobStore.getState().fetchJobs();

    const logs = getFlattenedJobLogs(useJobStore.getState().jobs);
    expect(logs.filter((entry) => entry.id === 'job-1:queued')).toHaveLength(1);
    expect(logs.filter((entry) => entry.id === 'evt-1')).toHaveLength(1);
  });

  it('preserves review_required as a terminal job status at 100% progress', () => {
    useJobStore.getState().mergeJobTimelineEvent({
      at: '2026-03-20T00:00:10.000Z',
      event_id: 'evt-review-1',
      job_id: 'job-review',
      message: 'manual review required',
      progress: 100,
      source: 'worker',
      status: 'review_required',
    });

    const job = useJobStore.getState().jobs.find((entry) => entry.job_id === 'job-review');
    expect(job?.status).toBe('review_required');
    expect(job?.progress).toBe(100);
  });

  it('persists structured download progress across websocket merge and api hydration', async () => {
    useJobStore.getState().mergeJobTimelineEvent({
      at: '2026-03-20T00:00:04.000Z',
      event_id: 'evt-download-1',
      job_id: 'job-2',
      message: 'indiriliyor',
      progress: 15,
      source: 'worker',
      status: 'processing',
      download_progress: {
        phase: 'download',
        downloaded_bytes: 1024,
        total_bytes: 4096,
        percent: 25,
        speed_text: '1.00MiB/s',
        eta_text: '00:03',
        status: 'downloading',
      },
    });

    listMock.mockResolvedValueOnce({
      jobs: [
        {
          job_id: 'job-2',
          url: 'https://youtube.com/watch?v=test456',
          style: 'TIKTOK',
          status: 'processing',
          progress: 15,
          last_message: 'indiriliyor',
          created_at: 2,
          download_progress: {
            phase: 'download',
            downloaded_bytes: 1024,
            total_bytes: 4096,
            percent: 25,
            speed_text: '1.00MiB/s',
            eta_text: '00:03',
            status: 'downloading',
          },
          timeline: [
            {
              id: 'evt-download-1',
              at: '2026-03-20T00:00:04.000Z',
              job_id: 'job-2',
              message: 'indiriliyor',
              progress: 15,
              source: 'worker',
              status: 'processing',
              download_progress: {
                phase: 'download',
                downloaded_bytes: 1024,
                total_bytes: 4096,
                percent: 25,
                speed_text: '1.00MiB/s',
                eta_text: '00:03',
                status: 'downloading',
              },
            },
          ],
        },
      ],
    });

    await useJobStore.getState().fetchJobs();

    const job = useJobStore.getState().jobs.find((entry) => entry.job_id === 'job-2');
    expect(job?.download_progress).toEqual({
      phase: 'download',
      downloaded_bytes: 1024,
      total_bytes: 4096,
      percent: 25,
      speed_text: '1.00MiB/s',
      eta_text: '00:03',
      status: 'downloading',
    });
    expect(job?.timeline?.[0]?.download_progress?.percent).toBe(25);
  });

  it('drops stale queued or processing jobs when the backend no longer knows about them', async () => {
    useJobStore.getState().registerQueuedJob({
      job_id: 'job-stale',
      message: 'queued now',
      style: 'TIKTOK',
      url: 'https://youtube.com/watch?v=test123',
    });

    listMock.mockResolvedValueOnce({ jobs: [] });

    await useJobStore.getState().fetchJobs();

    expect(useJobStore.getState().jobs).toEqual([]);
    expect(useJobStore.getState().hasRetainedHistory).toBe(false);
  });

  it('keeps completed history visible when backend hydration is empty but ttl is still active', async () => {
    useJobStore.getState().mergeJobTimelineEvent({
      at: '2026-03-20T00:00:04.000Z',
      event_id: 'evt-done',
      job_id: 'job-done',
      message: 'done',
      progress: 100,
      source: 'worker',
      status: 'completed',
    });

    listMock.mockResolvedValueOnce({ jobs: [] });

    await useJobStore.getState().fetchJobs();

    const state = useJobStore.getState();
    expect(state.jobs).toHaveLength(1);
    expect(state.jobs[0]?.status).toBe('completed');
    expect(state.jobHistoryExpiresAt).not.toBeNull();
  });
});

describe('useJobStore retention controls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-20T00:00:00.000Z'));
    localStorage.clear();
    authRuntimeState.canUseProtectedRequests = true;
    useJobStore.getState().reset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('clears retained history manually when no active jobs remain', () => {
    useJobStore.getState().mergeJobTimelineEvent({
      at: '2026-03-20T00:00:04.000Z',
      event_id: 'evt-done',
      job_id: 'job-done',
      message: 'done',
      progress: 100,
      source: 'worker',
      status: 'completed',
    });

    expect(useJobStore.getState().jobs).toHaveLength(1);

    useJobStore.getState().clearRetainedHistory();

    const state = useJobStore.getState();
    expect(state.jobs).toEqual([]);
    expect(state.clipReadyByJob).toEqual({});
    expect(state.jobHistoryExpiresAt).toBeNull();
    expect(state.hasRetainedHistory).toBe(false);
  });

  it('does not clear retained history manually while an active job exists', () => {
    useJobStore.getState().registerQueuedJob({
      job_id: 'job-1',
      message: 'queued now',
      style: 'TIKTOK',
      url: 'https://youtube.com/watch?v=test123',
    });

    useJobStore.getState().clearRetainedHistory();

    expect(useJobStore.getState().jobs).toHaveLength(1);
    expect(useJobStore.getState().jobs[0]?.status).toBe('queued');
  });

  it('auto clears completed history after five minutes', () => {
    useJobStore.getState().mergeJobTimelineEvent({
      at: '2026-03-20T00:00:04.000Z',
      event_id: 'evt-done',
      job_id: 'job-done',
      message: 'done',
      progress: 100,
      source: 'worker',
      status: 'completed',
    });

    expect(useJobStore.getState().jobHistoryExpiresAt).toBe(Date.now() + 5 * 60 * 1000);

    vi.advanceTimersByTime(5 * 60 * 1000);

    const state = useJobStore.getState();
    expect(state.jobs).toEqual([]);
    expect(state.hasRetainedHistory).toBe(false);
    expect(state.jobHistoryExpiresAt).toBeNull();
  });
});

describe('useJobStore clip-ready bookkeeping', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    localStorage.clear();
    authRuntimeState.canUseProtectedRequests = true;
    useJobStore.getState().reset();
  });

  it('does not create duplicate logs for clip_ready refresh signals', () => {
    useJobStore.getState().mergeJobTimelineEvent({
      at: '2026-03-20T00:00:02.000Z',
      event_id: 'clip-ready-1',
      job_id: 'manual_1',
      message: 'Klip hazir',
      progress: 91,
      source: 'clip_ready',
      status: 'processing',
    });
    useJobStore.getState().markClipReady({
      clipName: 'clip-1.mp4',
      job_id: 'manual_1',
      message: 'Klip hazir',
      progress: 91,
      projectId: 'proj-1',
      uiTitle: 'Hook',
      at: '2026-03-20T00:00:02.000Z',
    });

    const state = useJobStore.getState();
    const logs = getFlattenedJobLogs(state.jobs);

    expect(state.clipReadySignal).toBe(1);
    expect(state.clipReadyByJob.manual_1).toEqual([
      {
        at: '2026-03-20T00:00:02.000Z',
        clipName: 'clip-1.mp4',
        job_id: 'manual_1',
        message: 'Klip hazir',
        progress: 91,
        projectId: 'proj-1',
        uiTitle: 'Hook',
      },
    ]);
    expect(logs.filter((entry) => entry.id === 'clip-ready-1')).toHaveLength(1);
  });
});
