import { render } from '@testing-library/react';
import { beforeEach, vi } from 'vitest';

export const mockFetchJobs = vi.fn();
export const mockRegisterQueuedJob = vi.fn();
export const mockStart = vi.fn().mockRejectedValue(new Error('Network error'));

vi.mock('../../store/useJobStore', () => ({
  useJobStore: () => ({ fetchJobs: mockFetchJobs, registerQueuedJob: mockRegisterQueuedJob }),
}));

vi.mock('../../api/client', () => ({
  jobsApi: {
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
