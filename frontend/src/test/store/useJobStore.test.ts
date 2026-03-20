import { beforeEach, describe, expect, it, vi } from 'vitest';

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

describe('useJobStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authRuntimeState.canUseProtectedRequests = true;
    useJobStore.getState().reset();
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
    expect(logs).toHaveLength(1);
    expect(logs[0]).toMatchObject({
      id: 'job-1:queued',
      job_id: 'job-1',
      message: 'queued now',
      status: 'queued',
    });
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
