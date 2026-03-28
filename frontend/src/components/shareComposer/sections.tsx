import { AlertCircle, CalendarClock, CheckCircle2, ExternalLink, Link2, Loader2, Send, Share2, X } from 'lucide-react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { formatDateTime, normalizeLocale } from '../../i18n';
import type { Clip, PublishJob, ShareDraftContent, SocialAccount, SocialPlatform } from '../../types';
import { getPlatformLabel } from './helpers';
import type { ShareComposerController } from './useShareComposerController';

function formatPublishState(job: PublishJob): string {
  const state = job.state.replaceAll('_', ' ');
  const delivery = String(job.delivery_status ?? '').trim();
  if (!delivery || delivery === job.state) {
    return state;
  }
  return `${state} / ${delivery.replaceAll('_', ' ')}`;
}

export function ShareComposerLayout({
  clip,
  controller,
  onClose,
}: {
  clip: Clip;
  controller: ShareComposerController;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm p-4 md:p-8 overflow-y-auto">
      <div className="max-w-6xl mx-auto glass-card p-6 border-primary/20 space-y-5">
        <ShareComposerHeader clipName={clip.name} onClose={onClose} onOpenSocialWorkspace={controller.openSocialComposePage} />
        {!controller.projectId && <ProjectWarning />}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          <div className="xl:col-span-1 space-y-4">
            <ConnectionCard
              apiKey={controller.apiKey}
              connected={controller.connected}
              connectUrl={controller.connectUrl}
              connectionMode={controller.connectionMode}
              loading={controller.loading}
              managedConnectionPending={controller.managedConnectionPending}
              onApiKeyChange={controller.setApiKey}
              onConnect={controller.handleConnect}
              onDisconnect={controller.handleDisconnect}
              onManagedConnectOpen={controller.handleManagedConnectOpen}
              onRefresh={controller.handleRefreshConnection}
            />
            <AccountsCard
              accounts={controller.accounts}
              onToggleAccount={controller.toggleAccount}
              selectedAccountIds={controller.selectedAccountIds}
            />
          </div>
          <div className="xl:col-span-2 space-y-4">
            <ContentCard
              activeContent={controller.activeContent}
              draftState={controller.draftState}
              loading={controller.loading}
              onResetDrafts={controller.handleResetDrafts}
              onSelectPlatform={controller.setSelectedPlatform}
              onUpdateContent={controller.updateActiveContent}
              onUpdateHashtags={controller.updateActiveHashtags}
              selectedPlatform={controller.selectedPlatform}
            />
            <PublishCard
              error={controller.error}
              loading={controller.loading}
              projectAvailable={Boolean(controller.projectId)}
              publishing={controller.publishing}
              scheduleAt={controller.scheduleAt}
              success={controller.success}
              onPublish={controller.submitPublish}
              onScheduleAtChange={controller.setScheduleAt}
            />
            <JobsCard
              jobs={controller.jobs}
              onApprove={controller.handleApprove}
              onCancel={controller.handleCancel}
            />
          </div>
        </div>
        {controller.loading && <LoadingFooter />}
      </div>
    </div>
  );
}

function ShareComposerHeader({
  clipName,
  onClose,
  onOpenSocialWorkspace,
}: {
  clipName: string;
  onClose: () => void;
  onOpenSocialWorkspace: () => void;
}) {
  const { t } = useTranslation();

  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <h3 className="text-sm font-mono uppercase tracking-[0.2em] text-primary flex items-center gap-2">
          <Share2 className="w-4 h-4" />
          {t('shareComposer.title')}
        </h3>
        <p className="text-[11px] text-muted-foreground mt-1">{clipName}</p>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenSocialWorkspace}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-foreground/5 px-3 py-2 text-[11px] font-mono uppercase"
        >
          <ExternalLink className="w-3 h-3" />
          {t('app.social.openComposer')}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center justify-center rounded-full min-w-[36px] min-h-[36px] bg-foreground/10 hover:bg-foreground/20"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

function ProjectWarning() {
  const { t } = useTranslation();

  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300 flex items-center gap-2">
      <AlertCircle className="w-4 h-4" />
      {t('shareComposer.projectWarning')}
    </div>
  );
}

function ConnectionCard({
  apiKey,
  connected,
  connectUrl,
  connectionMode,
  loading,
  managedConnectionPending,
  onApiKeyChange,
  onConnect,
  onDisconnect,
  onManagedConnectOpen,
  onRefresh,
}: {
  apiKey: string;
  connected: boolean;
  connectUrl: string | null;
  connectionMode: 'managed' | 'manual_api_key';
  loading: boolean;
  managedConnectionPending: boolean;
  onApiKeyChange: (value: string) => void;
  onConnect: () => void;
  onDisconnect: () => void;
  onManagedConnectOpen: () => void;
  onRefresh: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const isManaged = connectionMode === 'managed';

  return (
    <div className="rounded-xl border border-border bg-foreground/5 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono uppercase text-muted-foreground">{t('shareComposer.connection.title')}</span>
        {connected ? (
          <span className="text-[11px] text-green-400 inline-flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            {t('shareComposer.connection.connected')}
          </span>
        ) : (
          <span className="text-[11px] text-muted-foreground">{t('shareComposer.connection.disconnected')}</span>
        )}
      </div>

      {isManaged ? (
        <div className="rounded-lg border border-border bg-background/40 px-3 py-2 text-xs text-muted-foreground">
          {t('shareComposer.connection.managedHint')}
        </div>
      ) : (
        <input
          value={apiKey}
          onChange={(event) => onApiKeyChange(event.target.value)}
          placeholder={t('shareComposer.connection.apiKeyPlaceholder')}
          className="w-full h-9 rounded-lg bg-background/70 border border-border px-3 text-xs"
          autoComplete="off"
        />
      )}

      <div className="flex gap-2">
        <ConnectionActions
          connected={connected}
          connectUrl={connectUrl}
          isManaged={isManaged}
          loading={loading}
          managedConnectionPending={managedConnectionPending}
          onConnect={onConnect}
          onDisconnect={onDisconnect}
          onManagedConnectOpen={onManagedConnectOpen}
          onRefresh={onRefresh}
        />
      </div>
    </div>
  );
}

function ConnectionActions({
  connected,
  connectUrl,
  isManaged,
  loading,
  managedConnectionPending,
  onConnect,
  onDisconnect,
  onManagedConnectOpen,
  onRefresh,
}: {
  connected: boolean;
  connectUrl: string | null;
  isManaged: boolean;
  loading: boolean;
  managedConnectionPending: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onManagedConnectOpen: () => void;
  onRefresh: () => Promise<void>;
}) {
  const { t } = useTranslation();

  if (isManaged) {
    return (
      <>
        {connectUrl ? (
          <a
            href={connectUrl}
            onClick={onManagedConnectOpen}
            className="flex-1 h-9 rounded-lg bg-primary/20 border border-primary/40 hover:bg-primary/30 text-xs font-mono uppercase inline-flex items-center justify-center"
          >
            {t('shareComposer.connection.openManaged')}
          </a>
        ) : null}
        <button
          type="button"
          onClick={() => void onRefresh()}
          disabled={loading}
          className="flex-1 h-9 rounded-lg bg-foreground/10 border border-border hover:bg-foreground/20 text-xs font-mono uppercase disabled:opacity-50"
        >
          {loading ? t('shareComposer.connection.refreshing') : t('shareComposer.connection.refreshAccounts')}
        </button>
        {managedConnectionPending ? (
          <div className="basis-full rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-100">
            {t('shareComposer.connection.returnHint')}
          </div>
        ) : null}
      </>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={onConnect}
        disabled={loading}
        className="flex-1 h-9 rounded-lg bg-primary/20 border border-primary/40 hover:bg-primary/30 text-xs font-mono uppercase disabled:opacity-50"
      >
        {loading ? t('shareComposer.connection.connecting') : t('shareComposer.connection.connect')}
      </button>
      <button
        type="button"
        onClick={onDisconnect}
        disabled={loading || !connected}
        className="flex-1 h-9 rounded-lg bg-foreground/10 border border-border hover:bg-foreground/20 text-xs font-mono uppercase disabled:opacity-50"
      >
        {t('shareComposer.connection.remove')}
      </button>
    </>
  );
}

function AccountsCard({
  accounts,
  onToggleAccount,
  selectedAccountIds,
}: {
  accounts: SocialAccount[];
  onToggleAccount: (accountId: string) => void;
  selectedAccountIds: string[];
}) {
  const { t } = useTranslation();

  return (
    <div className="rounded-xl border border-border bg-foreground/5 p-4 space-y-2">
      <div className="text-xs font-mono uppercase text-muted-foreground">{t('shareComposer.accounts.title')}</div>
      <div className="max-h-60 overflow-y-auto space-y-2 pr-1">
        {accounts.length === 0 && <p className="text-[11px] text-muted-foreground">{t('shareComposer.accounts.empty')}</p>}
        {accounts.map((account) => (
          <label
            key={account.id}
            className={`flex items-center gap-2 rounded-lg border px-2 py-2 text-xs ${account.requires_reconnect ? 'border-amber-500/40 bg-amber-500/10' : 'border-border cursor-pointer hover:bg-foreground/10'}`}
          >
            <input
              type="checkbox"
              checked={selectedAccountIds.includes(account.id)}
              onChange={() => onToggleAccount(account.id)}
              className="accent-primary"
              disabled={account.requires_reconnect}
            />
            <span className="min-w-0">
              <span className="block font-medium truncate">{account.name}</span>
              <span className="block text-[11px] text-muted-foreground">
                {getPlatformLabel(account.platform)}
                {account.requires_reconnect ? ' · reconnect required' : ''}
              </span>
              {account.requires_reconnect && account.health_error ? (
                <span className="block text-[11px] text-amber-100">{account.health_error}</span>
              ) : null}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

function ContentCard({
  activeContent,
  draftState,
  loading,
  onResetDrafts,
  onSelectPlatform,
  onUpdateContent,
  onUpdateHashtags,
  selectedPlatform,
}: {
  activeContent: ShareDraftContent | null;
  draftState: ShareComposerController['draftState'];
  loading: boolean;
  onResetDrafts: () => Promise<void>;
  onSelectPlatform: (platform: SocialPlatform) => void;
  onUpdateContent: (patch: Partial<ShareDraftContent>) => void;
  onUpdateHashtags: (value: string) => void;
  selectedPlatform: SocialPlatform;
}) {
  const { t } = useTranslation();

  return (
    <div className="rounded-xl border border-border bg-foreground/5 p-4 space-y-3">
      {(draftState.hasServerDrafts || draftState.hasLocalBuffer) && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span className="min-w-0">
              {t('shareComposer.content.draftLoaded')}
            </span>
          </div>
          <button
            type="button"
            onClick={() => void onResetDrafts()}
            disabled={loading}
            className="shrink-0 px-3 py-1.5 rounded-lg bg-background/50 border border-amber-300/30 hover:bg-background/70 text-[11px] font-mono uppercase disabled:opacity-50"
          >
            {t('shareComposer.content.resetToAi')}
          </button>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {(['youtube_shorts', 'tiktok', 'instagram_reels', 'facebook_reels', 'x', 'linkedin'] as SocialPlatform[]).map((platform) => (
          <button
            key={platform}
            type="button"
            onClick={() => onSelectPlatform(platform)}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-mono uppercase border transition-all ${selectedPlatform === platform
              ? 'bg-primary/20 border-primary/40 text-foreground'
              : 'bg-transparent border-border text-muted-foreground hover:text-foreground'}`}
          >
            {getPlatformLabel(platform)}
          </button>
        ))}
      </div>

      {!activeContent ? (
        <div className="text-xs text-muted-foreground">{t('shareComposer.content.loading')}</div>
      ) : (
        <ShareContentFields
          activeContent={activeContent}
          onUpdateContent={onUpdateContent}
          onUpdateHashtags={onUpdateHashtags}
        />
      )}
    </div>
  );
}

function ShareContentFields({
  activeContent,
  onUpdateContent,
  onUpdateHashtags,
}: {
  activeContent: ShareDraftContent;
  onUpdateContent: (patch: Partial<ShareDraftContent>) => void;
  onUpdateHashtags: (value: string) => void;
}) {
  const { t } = useTranslation();

  return (
    <>
      <label className="block text-[11px] text-muted-foreground uppercase">{t('shareComposer.content.titleLabel')}</label>
      <input
        value={activeContent.title ?? ''}
        onChange={(event) => onUpdateContent({ title: event.target.value })}
        className="w-full h-10 rounded-lg bg-background/70 border border-border px-3 text-sm"
      />

      <label className="block text-[11px] text-muted-foreground uppercase">{t('shareComposer.content.textLabel')}</label>
      <textarea
        value={activeContent.text ?? ''}
        onChange={(event) => onUpdateContent({ text: event.target.value })}
        className="w-full min-h-28 rounded-lg bg-background/70 border border-border px-3 py-2 text-sm resize-y"
      />

      <label className="block text-[11px] text-muted-foreground uppercase">{t('shareComposer.content.hashtagsLabel')}</label>
      <input
        value={(activeContent.hashtags ?? []).join(', ')}
        onChange={(event) => onUpdateHashtags(event.target.value)}
        className="w-full h-10 rounded-lg bg-background/70 border border-border px-3 text-sm"
      />
    </>
  );
}

function PublishCard({
  error,
  loading,
  projectAvailable,
  publishing,
  scheduleAt,
  success,
  onPublish,
  onScheduleAtChange,
}: {
  error: string | null;
  loading: boolean;
  projectAvailable: boolean;
  publishing: boolean;
  scheduleAt: string;
  success: string | null;
  onPublish: (mode: 'now' | 'scheduled', approvalRequired: boolean) => Promise<void>;
  onScheduleAtChange: (value: string) => void;
}) {
  const { t } = useTranslation();

  return (
    <div className="rounded-xl border border-border bg-foreground/5 p-4 space-y-3">
      <div className="flex flex-col md:flex-row gap-3 md:items-center">
        <div className="flex-1">
          <label className="block text-[11px] text-muted-foreground uppercase mb-1">{t('shareComposer.publish.scheduleAt')}</label>
          <input
            type="datetime-local"
            value={scheduleAt}
            onChange={(event) => onScheduleAtChange(event.target.value)}
            className="w-full h-10 rounded-lg bg-background/70 border border-border px-3 text-sm"
          />
        </div>
        <PublishButton
          disabled={publishing || !projectAvailable || loading}
          icon={publishing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          label={t('shareComposer.publish.now')}
          onClick={() => void onPublish('now', false)}
          tone="primary"
        />
        <PublishButton
          disabled={publishing || !projectAvailable || loading}
          icon={<CalendarClock className="w-3.5 h-3.5" />}
          label={t('shareComposer.publish.schedule')}
          onClick={() => void onPublish('scheduled', false)}
          tone="secondary"
        />
        <PublishButton
          disabled={publishing || !projectAvailable || loading}
          icon={<Link2 className="w-3.5 h-3.5" />}
          label={t('shareComposer.publish.approve')}
          onClick={() => void onPublish('scheduled', true)}
          tone="accent"
        />
      </div>
      {error && <StatusBanner message={error} tone="error" />}
      {success && <StatusBanner message={success} tone="success" />}
    </div>
  );
}

function PublishButton({
  disabled,
  icon,
  label,
  onClick,
  tone,
}: {
  disabled: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
  tone: 'accent' | 'primary' | 'secondary';
}) {
  const toneClass = tone === 'primary'
    ? 'bg-primary/20 border-primary/40 hover:bg-primary/30'
    : tone === 'secondary'
      ? 'bg-secondary/20 border-secondary/40 hover:bg-secondary/30'
      : 'bg-accent/20 border-accent/40 hover:bg-accent/30';

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`h-10 px-4 rounded-lg text-xs font-mono uppercase disabled:opacity-50 inline-flex items-center gap-2 ${toneClass}`}
    >
      {icon}
      {label}
    </button>
  );
}

function StatusBanner({ message, tone }: { message: string; tone: 'error' | 'success' }) {
  const icon = tone === 'error' ? <AlertCircle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />;
  const toneClass = tone === 'error'
    ? 'border-red-500/30 bg-red-500/10 text-red-300'
    : 'border-green-500/30 bg-green-500/10 text-green-300';

  return (
    <div className={`rounded-lg border px-3 py-2 text-xs flex items-center gap-2 ${toneClass}`} role={tone === 'error' ? 'alert' : undefined}>
      {icon}
      {message}
    </div>
  );
}

function JobsCard({
  jobs,
  onApprove,
  onCancel,
}: {
  jobs: PublishJob[];
  onApprove: (jobId: string) => Promise<void>;
  onCancel: (jobId: string) => Promise<void>;
}) {
  const { t, i18n } = useTranslation();
  const locale = normalizeLocale(i18n.language);

  return (
    <div className="rounded-xl border border-border bg-foreground/5 p-4 space-y-2">
      <div className="text-xs font-mono uppercase text-muted-foreground">{t('shareComposer.jobs.title')}</div>
      <div className="max-h-56 overflow-y-auto space-y-2 pr-1">
        {jobs.length === 0 && <p className="text-[11px] text-muted-foreground">{t('shareComposer.jobs.empty')}</p>}
        {jobs.map((job) => (
          <JobRow key={job.id} job={job} locale={locale} onApprove={onApprove} onCancel={onCancel} />
        ))}
      </div>
    </div>
  );
}

function JobRow({
  job,
  locale,
  onApprove,
  onCancel,
}: {
  job: PublishJob;
  locale: 'en' | 'tr';
  onApprove: (jobId: string) => Promise<void>;
  onCancel: (jobId: string) => Promise<void>;
}) {
  const { t } = useTranslation();

  return (
    <div className="rounded-lg border border-border px-3 py-2 text-xs bg-background/40">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{getPlatformLabel(job.platform)}</span>
        <span className="text-muted-foreground">{formatPublishState(job)}</span>
        {job.scheduled_at && <span className="text-muted-foreground">{formatDateTime(job.scheduled_at, locale)}</span>}
        {job.published_at && <span className="text-green-300">{formatDateTime(job.published_at, locale)}</span>}
        {job.last_error && <span className="text-red-300 truncate">{job.last_error}</span>}
        <span className="ml-auto text-[11px] text-muted-foreground">#{job.id.slice(0, 8)}</span>
      </div>
      <div className="mt-2 flex gap-2">
        {job.state === 'pending_approval' && (
          <button
            type="button"
            onClick={() => void onApprove(job.id)}
            className="px-2 py-1 rounded bg-primary/20 border border-primary/40 hover:bg-primary/30"
          >
            {t('shareComposer.jobs.approve')}
          </button>
        )}
        {!['published', 'failed', 'cancelled', 'publishing'].includes(job.state) && (
          <button
            type="button"
            onClick={() => void onCancel(job.id)}
            className="px-2 py-1 rounded bg-foreground/10 border border-border hover:bg-foreground/20"
          >
            {t('shareComposer.jobs.cancel')}
          </button>
        )}
      </div>
    </div>
  );
}

function LoadingFooter() {
  const { t } = useTranslation();

  return (
    <div className="text-xs text-muted-foreground inline-flex items-center gap-2">
      <Loader2 className="w-3.5 h-3.5 animate-spin" />
      {t('shareComposer.loading')}
    </div>
  );
}
