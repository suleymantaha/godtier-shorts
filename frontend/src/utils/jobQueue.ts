/**
 * frontend/src/utils/jobQueue.ts
 * ===============================
 * Kuyruk sırası ve proje meşguliyeti yardımcıları.
 */

import type { Job, JobStatus } from '../types';

export type { Job, JobStatus };

export function getQueuePosition(jobId: string | null | undefined, jobs: Job[]): number | null {
  if (!jobId) return null;
  const active = jobs
    .filter((j) => j.status === 'queued' || j.status === 'processing')
    .sort((a, b) => a.created_at - b.created_at);

  const idx = active.findIndex((j) => j.job_id === jobId);
  return idx >= 0 ? idx + 1 : null;
}

export function isProjectBusy(projectId: string | null | undefined, jobs: Job[]): boolean {
  if (!projectId) return false;
  return jobs.some(
    (j) =>
      j.project_id === projectId && (j.status === 'queued' || j.status === 'processing'),
  );
}
