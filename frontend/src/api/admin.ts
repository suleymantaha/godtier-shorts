import { apiFetch } from './client';

export interface AdminOverview {
  users: number;
  subscriptions: number;
  jobs: number;
  failed_jobs: number;
  risk_events: number;
  recent_users?: Array<{ id: string; status: string; role: string }>;
  recent_subscriptions?: Array<{ id: string; user_id: string; status: string }>;
  recent_jobs?: Array<{ id: string; user_id: string; status: string }>;
  recent_risk_events?: Array<{ id: number; user_id: string | null; signal: string; weight: number }>;
}

export interface JobEconomics {
  total_jobs: number;
  success_rate: number;
  review_required_rate: number;
  cost_per_source_hour_usd: string;
  cost_per_short_usd: string;
  average_queue_wait_seconds: number;
  average_render_seconds: number;
}

function operationKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `admin-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function reasonBody(reason: string): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  };
}

export const adminApi = {
  getOverview: () => apiFetch<AdminOverview>('/api/admin/overview'),
  getEconomics: () => apiFetch<JobEconomics>('/api/admin/job-economics'),
  adjustCredit: (userId: string, amount: number, reason: string) => apiFetch<{ available_credits: number }>(
    `/api/admin/users/${encodeURIComponent(userId)}/credit-adjustments`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operationKey() },
      body: JSON.stringify({ amount, reason }),
    },
  ),
  suspendUser: (userId: string, reason: string) => apiFetch<void>(
    `/api/admin/users/${encodeURIComponent(userId)}/suspend`,
    reasonBody(reason),
  ),
  syncSubscription: (subscriptionId: string, reason: string) => apiFetch<{ status: string }>(
    `/api/admin/subscriptions/${encodeURIComponent(subscriptionId)}/sync`,
    reasonBody(reason),
  ),
  retryJob: (jobId: string, reason: string) => apiFetch<{ status: string }>(
    `/api/admin/jobs/${encodeURIComponent(jobId)}/retry`,
    {
      ...reasonBody(reason),
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operationKey() },
    },
  ),
};
