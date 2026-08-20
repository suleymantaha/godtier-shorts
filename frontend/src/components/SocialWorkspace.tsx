import {
  AlertCircle,
  AlertTriangle,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  Clock,
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
  buildWeekStrip,
  deriveAttentionItems,
  formatDateTime,
  formatPublishState,
  platformLabel,
  ratioPercent,
  toDateTimeLocal,
  type AttentionItem,
  type AttentionReason,
  type SocialWorkspaceClipContext,
  type WeekStripDay,
} from './socialWorkspace/helpers';
import { useSocialWorkspaceController } from './socialWorkspace/useSocialWorkspaceController';

export function SocialWorkspace() {
  const controller = useSocialWorkspaceController();

  if (controller.loading) {
    return <LoadingState label={controller.t('socialWorkspace.loading')} />;
  }

  const attentionItems = deriveAttentionItems(controller.queue);
  const weekStrip = buildWeekStrip(controller.calendar, controller.locale, new Date());

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
      <section className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-6 items-start">
        <div className="space-y-6 min-w-0">
          <AttentionPanel
            items={attentionItems}
            onApprove={(job) => void controller.handleQueueAction(job, 'approve')}
            onCancel={(job) => void controller.handleQueueAction(job, 'cancel')}
            t={controller.t}
          />
          <WeekPanel
            calendar={controller.calendar}
            locale={controller.locale}
            onCancel={(job) => void controller.handleQueueAction(job, 'cancel')}
            onReschedule={controller.handleReschedule}
            t={controller.t}
            weekStrip={weekStrip}
          />
          <PerformancePanel
            accountAnalytics={controller.accountAnalytics}
            platformAnalytics={controller.platformAnalytics}
            t={controller.t}
          />
        </div>
        <ConnectionsRail
          onDeleteConnection={controller.handleDeleteConnection}
          onStartConnection={controller.handleStartConnection}
          providers={controller.providers}
          t={controller.t}
        />
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

const ATTENTION_REASON_KEY: Record<AttentionReason, string> = {
  failed: 'socialWorkspace.attention.failed',
  pending_approval: 'socialWorkspace.attention.pendingApproval',
  stalled: 'socialWorkspace.attention.stalled',
};

function AttentionPanel({
  items,
  onApprove,
  onCancel,
  t,
}: {
  items: AttentionItem[];
  onApprove: (job: PublishJob) => void;
  onCancel: (job: PublishJob) => void;
  t: TFunction;
}) {
  return (
    <Panel accent="amber" icon={<AlertTriangle className="w-4 h-4" />} title={t('socialWorkspace.attention.title')}>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('socialWorkspace.attention.empty')}</p>
      ) : (
        <div className="space-y-3">
          {items.map(({ job, reason }) => (
            <AttentionRow
              key={job.id}
              job={job}
              onApprove={() => onApprove(job)}
              onCancel={() => onCancel(job)}
              reason={reason}
              t={t}
            />
          ))}
        </div>
      )}
    </Panel>
  );
}

function AttentionRow({
  job,
  onApprove,
  onCancel,
  reason,
  t,
}: {
  job: PublishJob;
  onApprove: () => void;
  onCancel: () => void;
  reason: AttentionReason;
  t: TFunction;
}) {
  const composeHref = buildComposeHref(job.project_id, job.clip_name);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-background/40 p-4">
      <div className="min-w-0">
        <div className="text-sm font-semibold text-foreground truncate">{job.clip_name}</div>
        <div className="text-xs text-muted-foreground">
          {platformLabel(job.platform)} &middot; {t(ATTENTION_REASON_KEY[reason])}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {composeHref ? (
          <a href={composeHref} className="rounded-lg border border-primary/30 bg-primary/10 px-3 py-1 text-[11px] font-mono uppercase text-primary">
            {t('socialWorkspace.queue.openCompose')}
          </a>
        ) : null}
        {reason === 'pending_approval' ? (
          <button type="button" onClick={onApprove} className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[11px] font-mono uppercase text-emerald-100">
            {t('socialWorkspace.queue.approve')}
          </button>
        ) : null}
        <button type="button" onClick={onCancel} className="rounded-lg border border-border bg-foreground/5 px-3 py-1 text-[11px] font-mono uppercase text-muted-foreground">
          {t('common.actions.cancel')}
        </button>
      </div>
    </div>
  );
}

function WeekPanel({
  calendar,
  locale,
  onCancel,
  onReschedule,
  t,
  weekStrip,
}: {
  calendar: PublishJob[];
  locale: string;
  onCancel: (job: PublishJob) => void;
  onReschedule: (job: PublishJob, nextValue: string) => Promise<void>;
  t: TFunction;
  weekStrip: WeekStripDay[];
}) {
  return (
    <Panel icon={<CalendarDays className="w-4 h-4" />} title={t('socialWorkspace.week.title')}>
      <div className="grid grid-cols-7 gap-2 mb-4">
        {weekStrip.map((day) => (
          <div
            key={day.date.toISOString()}
            className={`rounded-xl border px-2 py-3 text-center ${day.isToday ? 'border-primary/40 bg-primary/10 text-primary' : 'border-border/70 bg-background/40 text-foreground'}`}
          >
            <div className="text-[10px] font-mono uppercase tracking-[0.08em] text-muted-foreground">{day.label}</div>
            <div className="mt-2 text-lg font-black">{day.count}</div>
          </div>
        ))}
      </div>
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
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground truncate">{job.clip_name}</div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {platformLabel(job.platform)} &middot; {formatPublishState(job)} &middot;
            <Clock className="w-3 h-3" />
            {formatDateTime(job.scheduled_at, locale)}
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
              {item.state} &middot; {item.message}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PerformancePanel({
  accountAnalytics,
  platformAnalytics,
  t,
}: {
  accountAnalytics: Array<{ account_id: string; account_name: string; published: number; total_jobs: number }>;
  platformAnalytics: Array<{ platform: string; published: number; total_jobs: number }>;
  t: TFunction;
}) {
  return (
    <Panel icon={<BarChart3 className="w-4 h-4" />} title={t('socialWorkspace.performance.title')}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <BarList
          emptyLabel={t('socialWorkspace.performance.empty')}
          rows={platformAnalytics.map((item) => ({
            id: item.platform,
            name: platformLabel(item.platform),
            published: item.published,
            totalJobs: item.total_jobs,
          }))}
          title={t('socialWorkspace.analytics.platforms')}
        />
        <BarList
          emptyLabel={t('socialWorkspace.performance.empty')}
          rows={accountAnalytics.map((item) => ({
            id: item.account_id,
            name: item.account_name,
            published: item.published,
            totalJobs: item.total_jobs,
          }))}
          title={t('socialWorkspace.analytics.accounts')}
        />
      </div>
    </Panel>
  );
}

function BarList({
  emptyLabel,
  rows,
  title,
}: {
  emptyLabel: string;
  rows: Array<{ id: string; name: string; published: number; totalJobs: number }>;
  title: string;
}) {
  return (
    <div>
      <div className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground mb-3">{title}</div>
      {rows.length === 0 ? (
        <div className="rounded-lg border border-border bg-background/40 px-3 py-2 text-xs text-muted-foreground">{emptyLabel}</div>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => {
            const percent = ratioPercent(row.published, row.totalJobs);
            return (
              <div key={row.id}>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-medium text-foreground truncate">{row.name}</span>
                  <span className="text-muted-foreground font-mono text-[11px]">{row.published}/{row.totalJobs}</span>
                </div>
                <div className="h-1.5 rounded-full bg-foreground/10 overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-primary to-secondary" style={{ width: `${percent}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ConnectionsRail({
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
    <Panel icon={<Link2 className="w-4 h-4" />} title={t('socialWorkspace.connections.title')}>
      <div className="space-y-3">
        {providers.map((provider) => (
          <div key={provider.platform} className="rounded-xl border border-border/70 bg-background/40 p-3 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-foreground truncate">{provider.title}</div>
              <button
                type="button"
                onClick={() => void onStartConnection(provider.platform)}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/15 px-2.5 py-1.5 text-[10px] font-mono uppercase"
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

function Panel({
  accent = 'default',
  children,
  icon,
  title,
}: {
  accent?: 'amber' | 'default';
  children: ReactNode;
  icon: ReactNode;
  title: string;
}) {
  const accentClass = accent === 'amber' ? 'border-amber-500/25' : 'border-accent/20';
  const titleClass = accent === 'amber' ? 'text-amber-300' : 'text-accent';

  return (
    <section className={`glass-card p-5 sm:p-6 space-y-4 ${accentClass}`}>
      <div className={`flex items-center gap-2 text-xs font-mono uppercase tracking-[0.18em] ${titleClass}`}>
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
