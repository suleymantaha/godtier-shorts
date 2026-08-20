import { SOCIAL_COMPOSE_PATH } from '../../app/helpers';
import type { PublishJob } from '../../types';

export type SocialWorkspaceClipContext = {
  clipName: string | null;
  projectId: string | null;
};

export function readSocialWorkspaceClipContext(locationSearch: string): SocialWorkspaceClipContext {
  const query = new URLSearchParams(locationSearch);
  return {
    clipName: query.get('clip_name'),
    projectId: query.get('project_id'),
  };
}

export function resolveSocialWorkspaceLocale(language: string): string {
  return language === 'tr' ? 'tr-TR' : 'en-US';
}

export function toDateTimeLocal(value?: string | null): string {
  if (!value) {
    return '';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hours = `${date.getHours()}`.padStart(2, '0');
  const minutes = `${date.getMinutes()}`.padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export function formatDateTime(value?: string | null, locale = 'en-US'): string {
  if (!value) {
    return '-';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale, {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

export function buildComposeHref(projectId?: string | null, clipName?: string | null): string | null {
  if (!projectId || !clipName) {
    return null;
  }

  const params = new URLSearchParams({
    project_id: projectId,
    clip_name: clipName,
  });
  return `${SOCIAL_COMPOSE_PATH}?${params.toString()}`;
}

export function platformLabel(value: string): string {
  return value.replaceAll('_', ' ');
}

export function formatPublishState(job: PublishJob): string {
  const state = job.state.replaceAll('_', ' ');
  const delivery = String(job.delivery_status ?? '').trim();
  if (!delivery || delivery === job.state) {
    return state;
  }

  return `${state} / ${delivery.replaceAll('_', ' ')}`;
}

export type AttentionReason = 'pending_approval' | 'failed' | 'stalled';

export interface AttentionItem {
  job: PublishJob;
  reason: AttentionReason;
}

export function deriveAttentionItems(queue: PublishJob[]): AttentionItem[] {
  const items: AttentionItem[] = [];

  for (const job of queue) {
    if (job.state === 'pending_approval') {
      items.push({ job, reason: 'pending_approval' });
    } else if (job.state === 'failed') {
      items.push({ job, reason: 'failed' });
    } else if (job.delivery_status === 'stalled') {
      items.push({ job, reason: 'stalled' });
    }
  }

  return items;
}

export interface WeekStripDay {
  count: number;
  date: Date;
  isToday: boolean;
  label: string;
}

export function buildWeekStrip(calendar: PublishJob[], locale: string, now: Date): WeekStripDay[] {
  const startOfWeek = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const mondayOffset = (startOfWeek.getDay() + 6) % 7;
  startOfWeek.setDate(startOfWeek.getDate() - mondayOffset);

  const formatter = new Intl.DateTimeFormat(locale, { weekday: 'short' });

  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(startOfWeek);
    date.setDate(date.getDate() + index);

    const count = calendar.filter((job) => {
      if (!job.scheduled_at) {
        return false;
      }
      const scheduled = new Date(job.scheduled_at);
      return scheduled.getFullYear() === date.getFullYear()
        && scheduled.getMonth() === date.getMonth()
        && scheduled.getDate() === date.getDate();
    }).length;

    return {
      count,
      date,
      isToday: date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate(),
      label: formatter.format(date),
    };
  });
}

export function ratioPercent(published: number, totalJobs: number): number {
  if (totalJobs <= 0) {
    return 0;
  }
  return Math.round((published / totalJobs) * 100);
}
