import { AlertCircle, BarChart3, CalendarDays, CheckCircle2, ExternalLink, Link2, Loader2, RefreshCcw, Send, Share2, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { socialApi } from '../api/client';
import { resolveApiUrl } from '../utils/url';
import type {
  PublishJob,
  ShareDraftContent,
  SocialAccount,
  SocialAccountAnalytics,
  SocialAnalyticsOverview,
  SocialPlatform,
  SocialPlatformAnalytics,
  SocialPostAnalytics,
  SocialProviderStatus,
} from '../types';

type ContentMap = Record<SocialPlatform, ShareDraftContent>;

const SOCIAL_PLATFORMS: SocialPlatform[] = ['youtube_shorts', 'tiktok', 'instagram_reels', 'facebook_reels', 'x', 'linkedin'];

function createEmptyContentMap(): ContentMap {
  return {
    facebook_reels: { hashtags: [], text: '', title: '' },
    instagram_reels: { hashtags: [], text: '', title: '' },
    linkedin: { hashtags: [], text: '', title: '' },
    tiktok: { hashtags: [], text: '', title: '' },
    x: { hashtags: [], text: '', title: '' },
    youtube_shorts: { hashtags: [], text: '', title: '' },
  };
}

function buildPublishTargets(accounts: SocialAccount[], selectedIds: string[], platform: SocialPlatform) {
  const idSet = new Set(selectedIds);
  return accounts
    .filter((account) => account.platform === platform && idSet.has(account.id))
    .map((account) => ({
      account_id: account.id,
      platform: account.platform,
      provider: account.provider ?? undefined,
    }));
}

function toDateTimeLocal(value?: string | null): string {
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

function fromHashtagInput(value: string): string[] {
  return value
    .split(',')
    .map((part) => part.trim().replace(/^#/, ''))
    .filter(Boolean);
}

export function SocialWorkspace() {
  const { t } = useTranslation();
  const query = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : new URLSearchParams();
  const [projectId, setProjectId] = useState(query.get('project_id') ?? '');
  const [clipName, setClipName] = useState(query.get('clip_name') ?? '');
  const [providers, setProviders] = useState<SocialProviderStatus[]>([]);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [queue, setQueue] = useState<PublishJob[]>([]);
  const [calendar, setCalendar] = useState<PublishJob[]>([]);
  const [overview, setOverview] = useState<SocialAnalyticsOverview | null>(null);
  const [platformAnalytics, setPlatformAnalytics] = useState<SocialPlatformAnalytics[]>([]);
  const [accountAnalytics, setAccountAnalytics] = useState<SocialAccountAnalytics[]>([]);
  const [postAnalytics, setPostAnalytics] = useState<SocialPostAnalytics[]>([]);
  const [contentByPlatform, setContentByPlatform] = useState<ContentMap>(createEmptyContentMap);
  const [selectedPlatform, setSelectedPlatform] = useState<SocialPlatform>('youtube_shorts');
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);
  const [mode, setMode] = useState<'now' | 'scheduled'>('now');
  const [scheduleAt, setScheduleAt] = useState(() => toDateTimeLocal(new Date(Date.now() + 60 * 60 * 1000).toISOString()));
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const filteredAccounts = useMemo(
    () => accounts.filter((account) => account.platform === selectedPlatform),
    [accounts, selectedPlatform],
  );
  const activeContent = contentByPlatform[selectedPlatform];

  const loadWorkspace = async (refreshAnalytics = false) => {
    setLoading(true);
    setError(null);
    try {
      const [providersResp, connectionsResp, queueResp, calendarResp, overviewResp, accountsResp, postsResp] = await Promise.all([
        socialApi.getProviders(),
        socialApi.getConnections(),
        socialApi.getQueue(),
        socialApi.getCalendar({ include_past: true }),
        socialApi.getAnalyticsOverview(refreshAnalytics),
        socialApi.getAnalyticsAccounts(refreshAnalytics),
        socialApi.getAnalyticsPosts(refreshAnalytics),
      ]);
      setProviders(providersResp.providers ?? []);
      setAccounts(connectionsResp.accounts ?? []);
      setQueue(queueResp.jobs ?? []);
      setCalendar(calendarResp.items ?? []);
      setOverview(overviewResp.overview ?? null);
      setPlatformAnalytics(overviewResp.platforms ?? []);
      setAccountAnalytics(accountsResp.accounts ?? []);
      setPostAnalytics(postsResp.posts ?? []);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t('socialWorkspace.errors.loadFailed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadWorkspace();
  }, []);

  useEffect(() => {
    if (!projectId || !clipName) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const prefill = await socialApi.getPrefill(projectId, clipName);
        if (cancelled) {
          return;
        }
        setContentByPlatform(prefill.platforms as ContentMap);
      } catch (prefillError) {
        if (!cancelled) {
          setError(prefillError instanceof Error ? prefillError.message : t('socialWorkspace.errors.prefillFailed'));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [clipName, projectId, t]);

  useEffect(() => {
    if (filteredAccounts.length === 0) {
      setSelectedAccountIds([]);
      return;
    }
    setSelectedAccountIds((current) => {
      const available = new Set(filteredAccounts.map((account) => account.id));
      const next = current.filter((id) => available.has(id));
      if (next.length > 0) {
        return next;
      }
      return [filteredAccounts[0].id];
    });
  }, [filteredAccounts]);

  const handleSyncConnections = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await socialApi.syncConnections();
      await loadWorkspace();
      setSuccess(t('socialWorkspace.connections.synced'));
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : t('socialWorkspace.errors.syncFailed'));
    } finally {
      setRefreshing(false);
    }
  };

  const handleStartConnection = async (platform: SocialPlatform) => {
    setRefreshing(true);
    setError(null);
    try {
      const response = await socialApi.startConnection({ platform, return_url: window.location.href });
      window.open(resolveApiUrl(response.launch_url), '_blank', 'noopener,noreferrer');
      setSuccess(t('socialWorkspace.connections.connectionStarted', { platform: providers.find((item) => item.platform === platform)?.title ?? platform }));
    } catch (connectError) {
      setError(connectError instanceof Error ? connectError.message : t('socialWorkspace.errors.connectionStartFailed'));
    } finally {
      setRefreshing(false);
    }
  };

  const handleDeleteConnection = async (accountId: string) => {
    setRefreshing(true);
    setError(null);
    try {
      await socialApi.deleteConnection(accountId);
      await handleSyncConnections();
    } catch (disconnectError) {
      setError(disconnectError instanceof Error ? disconnectError.message : t('socialWorkspace.errors.disconnectFailed'));
      setRefreshing(false);
    }
  };

  const handleRefreshAnalytics = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await loadWorkspace(true);
      setSuccess(t('socialWorkspace.analytics.refreshed'));
    } finally {
      setRefreshing(false);
    }
  };

  const handlePublish = async () => {
    if (!projectId || !clipName) {
      setError(t('socialWorkspace.composer.clipRequired'));
      return;
    }
    const targets = buildPublishTargets(accounts, selectedAccountIds, selectedPlatform);
    if (targets.length === 0) {
      setError(t('socialWorkspace.composer.accountRequired'));
      return;
    }

    setPublishing(true);
    setError(null);
    setSuccess(null);
    try {
      await socialApi.publish({
        project_id: projectId,
        clip_name: clipName,
        mode,
        scheduled_at: mode === 'scheduled' ? scheduleAt : undefined,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        targets,
        content_by_platform: contentByPlatform,
      });
      await loadWorkspace(true);
      setSuccess(mode === 'scheduled' ? t('socialWorkspace.composer.scheduledSuccess') : t('socialWorkspace.composer.publishedSuccess'));
    } catch (publishError) {
      setError(publishError instanceof Error ? publishError.message : t('socialWorkspace.errors.publishFailed'));
    } finally {
      setPublishing(false);
    }
  };

  const handleQueueAction = async (job: PublishJob, action: 'approve' | 'cancel') => {
    setRefreshing(true);
    setError(null);
    try {
      if (action === 'approve') {
        await socialApi.approveJob(job.id);
      } else {
        await socialApi.cancelJob(job.id);
      }
      await loadWorkspace(true);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : t('socialWorkspace.errors.queueActionFailed'));
    } finally {
      setRefreshing(false);
    }
  };

  const handleReschedule = async (job: PublishJob, nextValue: string) => {
    if (!nextValue) {
      return;
    }
    setRefreshing(true);
    setError(null);
    try {
      await socialApi.updateCalendarItem(job.id, {
        scheduled_at: nextValue,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      await loadWorkspace(true);
      setSuccess(t('socialWorkspace.calendar.updated'));
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : t('socialWorkspace.errors.calendarUpdateFailed'));
    } finally {
      setRefreshing(false);
    }
  };

  const toggleAccountSelection = (accountId: string) => {
    setSelectedAccountIds((current) => (
      current.includes(accountId)
        ? current.filter((item) => item !== accountId)
        : [...current, accountId]
    ));
  };

  const updateActiveContent = (patch: Partial<ShareDraftContent>) => {
    setContentByPlatform((current) => ({
      ...current,
      [selectedPlatform]: {
        ...current[selectedPlatform],
        ...patch,
      },
    }));
  };

  if (loading) {
    return (
      <main className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <div className="lg:col-span-12 glass-card border-accent/20 p-6 flex items-center gap-3">
          <Loader2 className="w-4 h-4 animate-spin text-primary" />
          {t('socialWorkspace.loading')}
        </div>
      </main>
    );
  }

  return (
    <main className="grid grid-cols-1 gap-8 items-start">
      <section className="glass-card border-accent/20 p-5 sm:p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-mono uppercase tracking-[0.2em] text-primary flex items-center gap-2">
              <Share2 className="w-4 h-4" />
              {t('socialWorkspace.title')}
            </h2>
            <p className="text-sm text-muted-foreground mt-2">{t('socialWorkspace.subtitle')}</p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void handleSyncConnections()}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-foreground/5 px-3 py-2 text-xs font-mono uppercase"
            >
              <RefreshCcw className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} />
              {t('socialWorkspace.actions.syncConnections')}
            </button>
            <button
              type="button"
              onClick={() => void handleRefreshAnalytics()}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-foreground/5 px-3 py-2 text-xs font-mono uppercase"
            >
              <BarChart3 className={`w-3 h-3 ${refreshing ? 'animate-pulse' : ''}`} />
              {t('socialWorkspace.actions.refreshAnalytics')}
            </button>
          </div>
        </div>
        {error ? (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        ) : null}
        {success ? (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            {success}
          </div>
        ) : null}
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        <OverviewCard label={t('socialWorkspace.overview.connectedAccounts')} value={String(overview?.connected_accounts ?? 0)} />
        <OverviewCard label={t('socialWorkspace.overview.totalJobs')} value={String(overview?.total_jobs ?? 0)} />
        <OverviewCard label={t('socialWorkspace.overview.scheduled')} value={String(overview?.scheduled ?? 0)} />
        <OverviewCard label={t('socialWorkspace.overview.successRate')} value={overview && overview.total_jobs > 0 ? `${Math.round((overview.published / overview.total_jobs) * 100)}%` : '0%'} />
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-[1.05fr_1.35fr] gap-6">
        <div className="space-y-6">
          <Panel title={t('socialWorkspace.connections.title')} icon={<Link2 className="w-4 h-4" />}>
            <div className="space-y-3">
              {providers.map((provider) => (
                <div key={provider.platform} className="rounded-xl border border-border/70 bg-background/40 p-3 space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-foreground">{provider.title}</div>
                      <div className="text-xs text-muted-foreground">{provider.description}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleStartConnection(provider.platform)}
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
                      <div key={account.id} className="inline-flex items-center gap-2 rounded-full border border-border bg-foreground/5 px-3 py-1 text-xs">
                        <span>{account.name}</span>
                        <button type="button" onClick={() => void handleDeleteConnection(account.id)} className="text-muted-foreground hover:text-red-300">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title={t('socialWorkspace.analytics.title')} icon={<BarChart3 className="w-4 h-4" />}>
            <div className="space-y-4">
              <AnalyticsTable
                title={t('socialWorkspace.analytics.platforms')}
                rows={platformAnalytics.map((item) => ({
                  id: item.platform,
                  name: item.platform,
                  meta: `${item.published}/${item.total_jobs} ${t('socialWorkspace.analytics.publishedShort')}`,
                }))}
              />
              <AnalyticsTable
                title={t('socialWorkspace.analytics.accounts')}
                rows={accountAnalytics.slice(0, 6).map((item) => ({
                  id: item.account_id,
                  name: item.account_name,
                  meta: `${item.published}/${item.total_jobs} ${t('socialWorkspace.analytics.publishedShort')}`,
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
        </div>

        <div className="space-y-6">
          <Panel title={t('socialWorkspace.composer.title')} icon={<Send className="w-4 h-4" />}>
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="space-y-2 text-xs text-muted-foreground">
                  <span>{t('socialWorkspace.composer.projectId')}</span>
                  <input value={projectId} onChange={(event) => setProjectId(event.target.value)} className="w-full rounded-lg border border-border bg-background/70 px-3 py-2 text-sm text-foreground" />
                </label>
                <label className="space-y-2 text-xs text-muted-foreground">
                  <span>{t('socialWorkspace.composer.clipName')}</span>
                  <input value={clipName} onChange={(event) => setClipName(event.target.value)} className="w-full rounded-lg border border-border bg-background/70 px-3 py-2 text-sm text-foreground" />
                </label>
              </div>
              {!projectId || !clipName ? (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
                  {t('socialWorkspace.composer.clipRequired')}
                </div>
              ) : null}
              <div className="flex flex-wrap gap-2">
                {SOCIAL_PLATFORMS.map((platform) => (
                  <button
                    key={platform}
                    type="button"
                    onClick={() => setSelectedPlatform(platform)}
                    className={`rounded-full px-3 py-1 text-xs border ${selectedPlatform === platform ? 'border-primary/50 bg-primary/15 text-primary' : 'border-border bg-foreground/5 text-muted-foreground'}`}
                  >
                    {platform}
                  </button>
                ))}
              </div>
              <label className="space-y-2 text-xs text-muted-foreground">
                <span>{t('socialWorkspace.composer.titleLabel')}</span>
                <input
                  value={activeContent.title}
                  onChange={(event) => updateActiveContent({ title: event.target.value })}
                  className="w-full rounded-lg border border-border bg-background/70 px-3 py-2 text-sm text-foreground"
                />
              </label>
              <label className="space-y-2 text-xs text-muted-foreground">
                <span>{t('socialWorkspace.composer.textLabel')}</span>
                <textarea
                  value={activeContent.text}
                  onChange={(event) => updateActiveContent({ text: event.target.value })}
                  rows={5}
                  className="w-full rounded-lg border border-border bg-background/70 px-3 py-2 text-sm text-foreground"
                />
              </label>
              <label className="space-y-2 text-xs text-muted-foreground">
                <span>{t('socialWorkspace.composer.hashtagsLabel')}</span>
                <input
                  value={activeContent.hashtags.join(', ')}
                  onChange={(event) => updateActiveContent({ hashtags: fromHashtagInput(event.target.value) })}
                  className="w-full rounded-lg border border-border bg-background/70 px-3 py-2 text-sm text-foreground"
                />
              </label>
              <div className="space-y-2">
                <div className="text-xs text-muted-foreground">{t('socialWorkspace.composer.accountsLabel')}</div>
                <div className="flex flex-wrap gap-2">
                  {filteredAccounts.length === 0 ? (
                    <span className="text-xs text-muted-foreground">{t('socialWorkspace.composer.noAccountsForPlatform')}</span>
                  ) : filteredAccounts.map((account) => (
                    <label key={account.id} className="inline-flex items-center gap-2 rounded-full border border-border bg-foreground/5 px-3 py-2 text-xs cursor-pointer">
                      <input type="checkbox" checked={selectedAccountIds.includes(account.id)} onChange={() => toggleAccountSelection(account.id)} />
                      {account.name}
                    </label>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="space-y-2 text-xs text-muted-foreground">
                  <span>{t('socialWorkspace.composer.modeLabel')}</span>
                  <select value={mode} onChange={(event) => setMode(event.target.value === 'scheduled' ? 'scheduled' : 'now')} className="w-full rounded-lg border border-border bg-background/70 px-3 py-2 text-sm text-foreground">
                    <option value="now">{t('socialWorkspace.composer.publishNow')}</option>
                    <option value="scheduled">{t('socialWorkspace.composer.schedule')}</option>
                  </select>
                </label>
                <label className="space-y-2 text-xs text-muted-foreground">
                  <span>{t('socialWorkspace.composer.scheduleAt')}</span>
                  <input type="datetime-local" value={scheduleAt} onChange={(event) => setScheduleAt(event.target.value)} disabled={mode !== 'scheduled'} className="w-full rounded-lg border border-border bg-background/70 px-3 py-2 text-sm text-foreground disabled:opacity-50" />
                </label>
              </div>
              <button
                type="button"
                onClick={() => void handlePublish()}
                disabled={publishing}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-primary/40 bg-primary/15 px-4 py-3 text-xs font-mono uppercase text-primary disabled:opacity-50"
              >
                {publishing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                {mode === 'scheduled' ? t('socialWorkspace.composer.schedule') : t('socialWorkspace.composer.publishNow')}
              </button>
            </div>
          </Panel>

          <Panel title={t('socialWorkspace.queue.title')} icon={<Share2 className="w-4 h-4" />}>
            <div className="space-y-3">
              {queue.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('socialWorkspace.queue.empty')}</p>
              ) : queue.slice(0, 12).map((job) => (
                <div key={job.id} className="rounded-xl border border-border bg-background/40 p-3 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-foreground">{job.clip_name}</div>
                      <div className="text-xs text-muted-foreground">{job.platform} · {job.state}</div>
                    </div>
                    <div className="flex gap-2">
                      {job.state === 'pending_approval' ? (
                        <button type="button" onClick={() => void handleQueueAction(job, 'approve')} className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[11px] font-mono uppercase text-emerald-100">
                          {t('socialWorkspace.queue.approve')}
                        </button>
                      ) : null}
                      {job.state !== 'cancelled' && job.state !== 'published' ? (
                        <button type="button" onClick={() => void handleQueueAction(job, 'cancel')} className="rounded-lg border border-border bg-foreground/5 px-3 py-1 text-[11px] font-mono uppercase text-muted-foreground">
                          {t('common.actions.cancel')}
                        </button>
                      ) : null}
                    </div>
                  </div>
                  {job.timeline?.length ? (
                    <div className="space-y-1">
                      {job.timeline.slice(-3).map((item) => (
                        <div key={`${job.id}:${item.at}:${item.state}`} className="text-[11px] text-muted-foreground">
                          {item.state} · {item.message}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </Panel>

          <Panel title={t('socialWorkspace.calendar.title')} icon={<CalendarDays className="w-4 h-4" />}>
            <div className="space-y-3">
              {calendar.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('socialWorkspace.calendar.empty')}</p>
              ) : calendar.map((job) => (
                <div key={job.id} className="rounded-xl border border-border bg-background/40 p-3 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-foreground">{job.clip_name}</div>
                      <div className="text-xs text-muted-foreground">{job.platform} · {job.state}</div>
                    </div>
                    <button type="button" onClick={() => void handleQueueAction(job, 'cancel')} className="rounded-lg border border-border bg-foreground/5 px-3 py-1 text-[11px] font-mono uppercase text-muted-foreground">
                      {t('common.actions.cancel')}
                    </button>
                  </div>
                  <input
                    type="datetime-local"
                    defaultValue={toDateTimeLocal(job.scheduled_at)}
                    onBlur={(event) => {
                      if (event.target.value && event.target.value !== toDateTimeLocal(job.scheduled_at)) {
                        void handleReschedule(job, event.target.value);
                      }
                    }}
                    className="w-full rounded-lg border border-border bg-background/70 px-3 py-2 text-sm text-foreground"
                  />
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </section>
    </main>
  );
}

function Panel({ children, icon, title }: { children: React.ReactNode; icon: React.ReactNode; title: string }) {
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
