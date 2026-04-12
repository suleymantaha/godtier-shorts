import {
  AlertCircle,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  ExternalLink,
  Link2,
  Loader2,
  RefreshCcw,
  Share2,
  Trash2,
} from 'lucide-react';
import type { TFunction } from 'i18next';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import type { PublishJob, SocialPlatform, SocialProviderStatus } from '../types';
import {
  buildComposeHref,
  formatDateTime,
  formatPublishState,
  platformLabel,
  toDateTimeLocal,
  type SocialWorkspaceClipContext,
} from './socialWorkspace/helpers';
import { useSocialWorkspaceController } from './socialWorkspace/useSocialWorkspaceController';

export function SocialWorkspace() {
  const controller = useSocialWorkspaceController();

  if (controller.loading) {
    return <LoadingState label={controller.t('socialWorkspace.loading')} />;
  }

  return (
    <main className="mx-auto max-w-[1500px] space-y-6">
      <WorkspaceHeader
        clipContext={controller.clipContext}
        contextComposeHref={controller.contextComposeHref}
        defaultComposeHref={controller.defaultComposeHref}
        error={controller.error}
        onRefreshAnalytics={controller.handleRefreshAnalytics}
        onSyncConnections={controller.handleSyncConnections}
        refreshing={controller.refreshing}
        success={controller.success}
        t={controller.t}
      />
      <OverviewGrid
        connectedAccountCount={controller.connectedAccountCount}
        overview={controller.overview}
        t={controller.t}
      />
      <section className="grid grid-cols-1 xl:grid-cols-[1.4fr_0.95fr] gap-6">
        <CalendarPanel
          calendar={controller.calendar}
          locale={controller.locale}
          onCancel={(job) => void controller.handleQueueAction(job, 'cancel')}
          onReschedule={controller.handleReschedule}
          t={controller.t}
        />
        <div className="space-y-6">
          <ConnectionsPanel
            onDeleteConnection={controller.handleDeleteConnection}
            onStartConnection={controller.handleStartConnection}
            providers={controller.providers}
            t={controller.t}
          />
          <QueuePanel
            onApprove={(job) => void controller.handleQueueAction(job, 'approve')}
            onCancel={(job) => void controller.handleQueueAction(job, 'cancel')}
            queue={controller.queue}
            t={controller.t}
          />
          <AnalyticsPanel
            accountAnalytics={controller.accountAnalytics}
            platformAnalytics={controller.platformAnalytics}
            postAnalytics={controller.postAnalytics}
            t={controller.t}
          />
        </div>
      </section>
    </main>
  );
}

function LoadingState({ label }: { label: string }) {
  return (
    <main className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <div className="lg:col-span-12 glass-card border-accent/20 p-6 flex items-center gap-3">
        <Loader2 className="w-4 h-4 animate-spin text-primary" />
        {label}
      </div>
    </main>
  );
}

function WorkspaceHeader({
  clipContext,
  contextComposeHref,
  defaultComposeHref,
  error,
  onRefreshAnalytics,
  onSyncConnections,
  refreshing,
  success,
  t,
}: {
  clipContext: SocialWorkspaceClipContext;
  contextComposeHref: string | null;
  defaultComposeHref: string;
  error: string | null;
  onRefreshAnalytics: () => Promise<void>;
  onSyncConnections: () => Promise<void>;
  refreshing: boolean;
  success: string | null;
  t: TFunction;
}) {
  const composeHref = contextComposeHref ?? defaultComposeHref;
  const composeLabel = contextComposeHref
    ? t('socialWorkspace.actions.openContextCompose')
    : t('socialWorkspace.actions.openCompose');

  return (
    <section className="glass-card border-accent/20 p-5 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h2 className="text-sm font-mono uppercase tracking-[0.2em] text-primary flex items-center gap-2">
            <Share2 className="w-4 h-4" />
            {t('socialWorkspace.title')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('socialWorkspace.subtitle')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void onSyncConnections()}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-foreground/5 px-3 py-2 text-xs font-mono uppercase"
          >
            <RefreshCcw className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} />
            {t('socialWorkspace.actions.syncConnections')}
          </button>
          <button
            type="button"
            onClick={() => void onRefreshAnalytics()}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-foreground/5 px-3 py-2 text-xs font-mono uppercase"
          >
            <BarChart3 className={`w-3 h-3 ${refreshing ? 'animate-pulse' : ''}`} />
            {t('socialWorkspace.actions.refreshAnalytics')}
          </button>
          <a
            href={composeHref}
            className="inline-flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/15 px-3 py-2 text-xs font-mono uppercase text-primary"
          >
            <ExternalLink className="w-3 h-3" />
            {composeLabel}
          </a>
        </div>
      </div>
      {clipContext.projectId || clipContext.clipName ? (
        <div className="rounded-xl border border-secondary/25 bg-secondary/10 px-4 py-3 text-xs text-secondary-foreground">
          {t('socialWorkspace.context.active', {
            clip: clipContext.clipName ?? t('socialWorkspace.context.none'),
            project: clipContext.projectId ?? t('socialWorkspace.context.none'),
          })}
        </div>
      ) : null}
      {error ? <FeedbackBanner tone="error">{error}</FeedbackBanner> : null}
      {success ? <FeedbackBanner tone="success">{success}</FeedbackBanner> : null}
    </section>
  );
}

function FeedbackBanner({
  children,
  tone,
}: {
  children: ReactNode;
  tone: 'error' | 'success';
}) {
  const config = tone === 'error'
    ? {
      className: 'rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200 flex items-center gap-2',
      icon: <AlertCircle className="w-4 h-4" />,
    }
    : {
      className: 'rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100 flex items-center gap-2',
      icon: <CheckCircle2 className="w-4 h-4" />,
    };

  return (
    <div className={config.className}>
      {config.icon}
      {children}
    </div>
  );
}

function OverviewGrid({
  connectedAccountCount,
  overview,
  t,
}: {
  connectedAccountCount: number;
  overview: { connected_accounts?: number; published: number; scheduled: number; total_jobs: number } | null;
  t: TFunction;
}) {
  const successRate = overview && overview.total_jobs > 0
    ? `${Math.round((overview.published / overview.total_jobs) * 100)}%`
    : '0%';

  return (
    <section className="grid grid-cols-1 xl:grid-cols-4 gap-4">
      <OverviewCard label={t('socialWorkspace.overview.connectedAccounts')} value={String(overview?.connected_accounts ?? connectedAccountCount)} />
      <OverviewCard label={t('socialWorkspace.overview.totalJobs')} value={String(overview?.total_jobs ?? 0)} />
      <OverviewCard label={t('socialWorkspace.overview.scheduled')} value={String(overview?.scheduled ?? 0)} />
      <OverviewCard label={t('socialWorkspace.overview.successRate')} value={successRate} />
    </section>
  );
}

function CalendarPanel({
  calendar,
  locale,
  onCancel,
  onReschedule,
  t,
}: {
  calendar: PublishJob[];
  locale: string;
  onCancel: (job: PublishJob) => void;
  onReschedule: (job: PublishJob, nextValue: string) => Promise<void>;
  t: TFunction;
}) {
  return (
    <div className="space-y-6">
      <Panel title={t('socialWorkspace.calendar.title')} icon={<CalendarDays className="w-4 h-4" />}>
        {calendar.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('socialWorkspace.calendar.empty')}</p>
        ) : (
          <div className="space-y-3">
            {calendar.map((job) => (
              <CalendarRow
                key={job.id}
                job={job}
                locale={locale}
                onCancel={() => onCancel(job)}
                onReschedule={(value) => void onReschedule(job, value)}
              />
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}

function ConnectionsPanel({
  onDeleteConnection,
  onStartConnection,
  providers,
  t,
}: {
  onDeleteConnection: (accountId: string) => Promise<void>;
  onStartConnection: (platform: SocialPlatform) => Promise<void>;
  providers: SocialProviderStatus[];
  t: TFunction;
}) {
  return (
    <Panel title={t('socialWorkspace.connections.title')} icon={<Link2 className="w-4 h-4" />}>
      <div className="space-y-3">
        {providers.map((provider) => (
          <div key={provider.platform} className="rounded-xl border border-border/70 bg-background/40 p-3 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-foreground">{provider.title}</div>
                <div className="text-xs text-muted-foreground">{provider.description}</div>
              </div>
              <button
                type="button"
                onClick={() => void onStartConnection(provider.platform)}
                className="inline-flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/15 px-3 py-2 text-[11px] font-mono uppercase"
              >
                <ExternalLink className="w-3 h-3" />
                {t('socialWorkspace.connections.connect')}
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {provider.accounts.length === 0 ? (
                <span className="text-xs text-muted-foreground">{t('socialWorkspace.connections.noAccounts')}</span>
              ) : provider.accounts.map((account) => (
                <div key={account.id} className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${account.requires_reconnect ? 'border-amber-500/40 bg-amber-500/10 text-amber-100' : 'border-border bg-foreground/5'}`}>
                  <span>{account.name}</span>
                  {account.requires_reconnect ? <span className="text-[10px] uppercase">Reconnect</span> : null}
                  <button type="button" onClick={() => void onDeleteConnection(account.id)} className="text-muted-foreground hover:text-red-300">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function QueuePanel({
  onApprove,
  onCancel,
  queue,
  t,
}: {
  onApprove: (job: PublishJob) => void;
  onCancel: (job: PublishJob) => void;
  queue: PublishJob[];
  t: TFunction;
}) {
  return (
    <Panel title={t('socialWorkspace.queue.title')} icon={<Share2 className="w-4 h-4" />}>
      <div className="space-y-3">
        {queue.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('socialWorkspace.queue.empty')}</p>
        ) : queue.slice(0, 12).map((job) => (
          <QueueRow
            key={job.id}
            job={job}
            onApprove={() => onApprove(job)}
            onCancel={() => onCancel(job)}
          />
        ))}
      </div>
    </Panel>
  );
}

function AnalyticsPanel({
  accountAnalytics,
  platformAnalytics,
  postAnalytics,
  t,
}: {
  accountAnalytics: Array<{ account_id: string; account_name: string; published: number; total_jobs: number }>;
  platformAnalytics: Array<{ platform: string; published: number; total_jobs: number }>;
  postAnalytics: Array<{ account_id: string; account_name: string; clip_name: string; latest_state: string; project_id: string }>;
  t: TFunction;
}) {
  const publishedShortLabel = t('socialWorkspace.analytics.publishedShort');

  return (
    <Panel title={t('socialWorkspace.analytics.title')} icon={<BarChart3 className="w-4 h-4" />}>
      <div className="space-y-4">
        <AnalyticsTable
          title={t('socialWorkspace.analytics.platforms')}
          rows={platformAnalytics.map((item) => ({
            id: item.platform,
            name: platformLabel(item.platform),
            meta: `${item.published}/${item.total_jobs} ${publishedShortLabel}`,
          }))}
        />
        <AnalyticsTable
          title={t('socialWorkspace.analytics.accounts')}
          rows={accountAnalytics.slice(0, 6).map((item) => ({
            id: item.account_id,
            name: item.account_name,
            meta: `${item.published}/${item.total_jobs} ${publishedShortLabel}`,
          }))}
        />
        <AnalyticsTable
          title={t('socialWorkspace.analytics.posts')}
          rows={postAnalytics.slice(0, 6).map((item) => ({
            id: `${item.project_id}:${item.clip_name}:${item.account_id}`,
            name: item.clip_name,
            meta: `${item.account_name} · ${item.latest_state}`,
          }))}
        />
      </div>
    </Panel>
  );
}

function CalendarRow({
  job,
  locale,
  onCancel,
  onReschedule,
}: {
  job: PublishJob;
  locale: string;
  onCancel: () => void;
  onReschedule: (value: string) => void;
}) {
  const { t } = useTranslation();
  const composeHref = buildComposeHref(job.project_id, job.clip_name);

  return (
    <div className="rounded-xl border border-border bg-background/40 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-foreground">{job.clip_name}</div>
          <div className="text-xs text-muted-foreground">
            {platformLabel(job.platform)} · {formatPublishState(job)} · {formatDateTime(job.scheduled_at, locale)}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {composeHref ? (
            <a href={composeHref} className="rounded-lg border border-primary/30 bg-primary/10 px-3 py-1 text-[11px] font-mono uppercase text-primary">
              {t('socialWorkspace.calendar.openCompose')}
            </a>
          ) : null}
          <button type="button" onClick={onCancel} className="rounded-lg border border-border bg-foreground/5 px-3 py-1 text-[11px] font-mono uppercase text-muted-foreground">
            {t('common.actions.cancel')}
          </button>
        </div>
      </div>
      <input
        type="datetime-local"
        defaultValue={toDateTimeLocal(job.scheduled_at)}
        onBlur={(event) => {
          if (event.target.value && event.target.value !== toDateTimeLocal(job.scheduled_at)) {
            onReschedule(event.target.value);
          }
        }}
        className="w-full rounded-lg border border-border bg-background/70 px-3 py-2 text-sm text-foreground"
      />
      {job.timeline?.length ? (
        <div className="space-y-1">
          {job.last_error ? (
            <div className="text-[11px] text-red-300">{job.last_error}</div>
          ) : null}
          {job.timeline.slice(-3).map((item) => (
            <div key={`${job.id}:${item.at}:${item.state}`} className="text-[11px] text-muted-foreground">
              {item.state} · {item.message}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function QueueRow({
  job,
  onApprove,
  onCancel,
}: {
  job: PublishJob;
  onApprove: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const composeHref = buildComposeHref(job.project_id, job.clip_name);

  return (
    <div className="rounded-xl border border-border bg-background/40 p-3 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-foreground">{job.clip_name}</div>
          <div className="text-xs text-muted-foreground">{platformLabel(job.platform)} · {formatPublishState(job)}</div>
        </div>
        <div className="flex gap-2">
          {composeHref ? (
            <a href={composeHref} className="rounded-lg border border-primary/30 bg-primary/10 px-3 py-1 text-[11px] font-mono uppercase text-primary">
              {t('socialWorkspace.queue.openCompose')}
            </a>
          ) : null}
          {job.state === 'pending_approval' ? (
            <button type="button" onClick={onApprove} className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[11px] font-mono uppercase text-emerald-100">
              {t('socialWorkspace.queue.approve')}
            </button>
          ) : null}
          {job.state !== 'cancelled' && job.state !== 'published' ? (
            <button type="button" onClick={onCancel} className="rounded-lg border border-border bg-foreground/5 px-3 py-1 text-[11px] font-mono uppercase text-muted-foreground">
              {t('common.actions.cancel')}
            </button>
          ) : null}
        </div>
      </div>
      {job.timeline?.length ? (
        <div className="space-y-1">
          {job.last_error ? (
            <div className="text-[11px] text-red-300">{job.last_error}</div>
          ) : null}
          {job.timeline.slice(-3).map((item) => (
            <div key={`${job.id}:${item.at}:${item.state}`} className="text-[11px] text-muted-foreground">
              {item.state} · {item.message}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Panel({ children, icon, title }: { children: ReactNode; icon: ReactNode; title: string }) {
  return (
    <section className="glass-card border-white/10 p-5 sm:p-6 space-y-4">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.18em] text-accent">
        {icon}
        {title}
      </div>
      {children}
    </section>
  );
}

function OverviewCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-card border-white/10 p-4">
      <div className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
      <div className="mt-2 text-3xl font-black tracking-tight text-foreground">{value}</div>
    </div>
  );
}

function AnalyticsTable({
  rows,
  title,
}: {
  rows: Array<{ id: string; name: string; meta: string }>;
  title: string;
}) {
  return (
    <div className="space-y-2">
      <div className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">{title}</div>
      <div className="space-y-2">
        {rows.length === 0 ? (
          <div className="rounded-lg border border-border bg-background/40 px-3 py-2 text-xs text-muted-foreground">No data</div>
        ) : rows.map((row) => (
          <div key={row.id} className="rounded-lg border border-border bg-background/40 px-3 py-2">
            <div className="text-sm font-medium text-foreground truncate">{row.name}</div>
            <div className="text-xs text-muted-foreground">{row.meta}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
