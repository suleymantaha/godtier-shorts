import { render } from '@testing-library/react';
import { beforeEach, vi } from 'vitest';

export const mockFetchJobs = vi.fn();
export const mockMergeJobTimelineEvent = vi.fn();
export const mockRegisterQueuedJob = vi.fn();
export const mockRequestClipsRefresh = vi.fn();
export const mockCacheStatus = vi.fn().mockResolvedValue({
  project_id: null,
  project_cached: false,
  analysis_cached: false,
  render_cached: false,
  cache_scope: 'none',
  clip_count: 0,
  message: '',
});
export const mockStart = vi.fn().mockRejectedValue(new Error('Network error'));

vi.mock('../../store/useJobStore', () => ({
  useJobStore: () => ({
    fetchJobs: mockFetchJobs,
    mergeJobTimelineEvent: mockMergeJobTimelineEvent,
    registerQueuedJob: mockRegisterQueuedJob,
    requestClipsRefresh: mockRequestClipsRefresh,
  }),
}));

vi.mock('../../api/client', () => ({
  jobsApi: {
    cacheStatus: (...args: unknown[]) => mockCacheStatus(...args),
    start: (...args: unknown[]) => mockStart(...args),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

export async function renderJobForm() {
  const { JobForm } = await import('../../components/JobForm');

  return render(<JobForm />);
}
