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
