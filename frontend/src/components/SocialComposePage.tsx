import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  Hash,
  Loader2,
  Send,
  Sparkles,
  Wand2,
} from 'lucide-react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { clipsApi } from '../api/client';
import type { Clip, ShareDraftContent, SocialAccount, SocialPlatform } from '../types';
import { getClipUrl } from '../utils/url';
import { buildSocialComposeUrl, getPlatformLabel, resolveProjectId } from './shareComposer/helpers';
import { useShareComposerController } from './shareComposer/useShareComposerController';

function readClipFromQuery(): Clip | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const params = new URLSearchParams(window.location.search);
  const clipName = params.get('clip_name');
  const projectId = params.get('project_id');
  const clipUrl = params.get('clip_url') ?? (projectId ? buildFallbackClipUrl(projectId, clipName) : null);

  if (!clipName || !clipUrl) {
    return null;
  }

  const createdAtRaw = Number(params.get('clip_created_at'));
  const durationRaw = Number(params.get('clip_duration'));

  return {
    created_at: Number.isFinite(createdAtRaw) ? createdAtRaw : Date.now(),
    duration: Number.isFinite(durationRaw) ? durationRaw : null,
    has_transcript: true,
    name: clipName,
    project: projectId ?? undefined,
    resolved_project_id: projectId ?? null,
    ui_title: params.get('clip_title') ?? undefined,
    url: clipUrl,
  };
}

function buildFallbackClipUrl(projectId: string, clipName: string | null): string | null {
  if (!clipName) {
    return null;
  }

  return `/api/projects/${encodeURIComponent(projectId)}/files/clip/${encodeURIComponent(clipName)}`;
}

function normalizeSearchValue(value: string): string {
  return value
    .toLocaleLowerCase('tr-TR')
    .normalize('NFKD')
    .replace(/\p{Diacritic}/gu, '');
}

function clipIdentityKey(clip: Clip): string {
  return `${clip.project ?? clip.resolved_project_id ?? 'legacy'}:${clip.name}`;
}

function buildKeywordHints(content: ShareDraftContent): string[] {
  const seen = new Set<string>();
  const hints: string[] = [];

  for (const tag of content.hashtags) {
    const normalized = tag.trim().replace(/^#/, '');
    if (!normalized) {
      continue;
    }
    const key = normalized.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    hints.push(normalized);
    if (hints.length >= 5) {
      return hints;
    }
  }

  for (const source of [content.title, content.hook_text ?? '', content.text]) {
    for (const token of source.split(/[\s,.:;!?()[\]{}"'`/\\-]+/)) {
      const normalized = token.trim();
      if (normalized.length < 4) {
        continue;
      }
      const key = normalized.toLowerCase();
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      hints.push(normalized);
      if (hints.length >= 5) {
        return hints;
      }
    }
  }

  return hints;
}

function defaultCtaForPlatform(platform: SocialPlatform): string {
  if (platform === 'x') {
    return 'Reply with your take.';
  }
  if (platform === 'linkedin') {
    return 'What would you add?';
  }
  return 'Follow for the next part.';
}

export function SocialComposePage() {
  const { t } = useTranslation();
  const [clip, setClip] = useState<Clip | null>(() => readClipFromQuery());
  const [clipOptions, setClipOptions] = useState<Clip[]>([]);
  const [clipQuery, setClipQuery] = useState('');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const controller = useShareComposerController({ clip, open: true });
  const previewUrl = useMemo(
    () => (clip ? getClipUrl(clip, { cacheBust: clip.created_at }) : null),
    [clip],
  );
  const filteredClipOptions = useMemo(() => {
    const query = normalizeSearchValue(clipQuery.trim());
    if (!query) {
      return clipOptions;
    }

    return clipOptions.filter((candidate) => {
      const title = normalizeSearchValue(candidate.ui_title ?? '');
      const name = normalizeSearchValue(candidate.name);
      return title.includes(query) || name.includes(query);
    });
  }, [clipOptions, clipQuery]);
  const activeContent = controller.activeContent;
  const selectedPlatformAccounts = useMemo(
    () => controller.accounts.filter((account) => account.platform === controller.selectedPlatform),
    [controller.accounts, controller.selectedPlatform],
  );

  useEffect(() => {
    let cancelled = false;
    setPickerLoading(true);
    setPickerError(null);
    void (async () => {
      try {
        const response = await clipsApi.list(1, 120);
        if (cancelled) {
          return;
        }
        setClipOptions(response.clips ?? []);
      } catch (error) {
        if (!cancelled) {
          setPickerError(error instanceof Error ? error.message : t('socialComposePage.clipPicker.error'));
        }
      } finally {
        if (!cancelled) {
          setPickerLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [t]);

  const handleSelectClip = (selectedClip: Clip) => {
    setClip(selectedClip);
    setPickerOpen(false);
    if (typeof window === 'undefined') {
      return;
    }
    window.history.replaceState({}, '', buildSocialComposeUrl(selectedClip));
  };

  return (
    <main className="mx-auto max-w-[1500px] space-y-6">
      <section className="glass-card border-secondary/20 p-6 sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-secondary/30 bg-secondary/12 px-3 py-1 text-[11px] font-mono uppercase tracking-[0.2em] text-secondary">
              <Wand2 className="h-3.5 w-3.5" />
              {t('socialComposePage.title')}
            </div>
            <div>
              <h1 className="text-3xl font-black tracking-tight text-foreground sm:text-4xl">
                {clip?.ui_title || clip?.name || t('socialComposePage.clipPicker.choose')}
              </h1>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{t('socialComposePage.subtitle')}</p>
            </div>
            <div className="flex flex-wrap gap-2 text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
              <span className="rounded-full border border-border bg-foreground/5 px-3 py-1">{clip ? (resolveProjectId(clip) ?? 'no-project') : 'clip-not-selected'}</span>
              <span className="rounded-full border border-border bg-foreground/5 px-3 py-1">{clip?.name ?? t('socialComposePage.clipPicker.choose')}</span>
              <span className="rounded-full border border-border bg-foreground/5 px-3 py-1">{getPlatformLabel(controller.selectedPlatform)}</span>
            </div>
          </div>
          <div className="w-full max-w-xl space-y-2">
            <input
              type="search"
              value={clipQuery}
              onChange={(event) => setClipQuery(event.target.value)}
              placeholder={t('socialComposePage.clipPicker.searchPlaceholder')}
              className="w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-sm text-foreground focus:border-secondary/60 focus:outline-none"
            />
            <div className="relative">
              <button
                type="button"
                onClick={() => setPickerOpen((open) => !open)}
                className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-background/70 px-3 py-2 text-left"
                aria-expanded={pickerOpen}
                aria-label={t('socialComposePage.clipPicker.label')}
              >
                {clip ? (
                  <div className="flex min-w-0 items-center gap-3">
                    <video
                      src={getClipUrl(clip, { cacheBust: clip.created_at })}
                      className="h-10 w-16 rounded-md border border-border bg-black object-cover"
                      muted
                      playsInline
                      preload="metadata"
                    />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-foreground">{clip.ui_title || clip.name}</div>
                      <div className="truncate text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground">{resolveProjectId(clip) ?? 'no-project'}</div>
                    </div>
                  </div>
                ) : (
                  <span className="text-sm text-muted-foreground">{t('socialComposePage.clipPicker.choose')}</span>
                )}
                <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${pickerOpen ? 'rotate-180' : ''}`} />
              </button>
              {pickerOpen ? (
                <div className="absolute z-50 mt-2 max-h-80 w-full overflow-y-auto rounded-xl border border-border bg-background/95 p-2 shadow-2xl">
                  {pickerLoading ? (
                    <div className="flex items-center gap-2 px-2 py-2 text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      {t('socialComposePage.clipPicker.loading')}
                    </div>
                  ) : pickerError ? (
                    <div className="px-2 py-2 text-sm text-red-300">{pickerError}</div>
                  ) : filteredClipOptions.length === 0 ? (
                    <div className="px-2 py-2 text-sm text-muted-foreground">{t('socialComposePage.clipPicker.empty')}</div>
                  ) : (
                    filteredClipOptions.map((candidate) => (
                      <button
                        key={clipIdentityKey(candidate)}
                        type="button"
                        onClick={() => handleSelectClip(candidate)}
                        className={`mb-1 flex w-full items-center gap-3 rounded-lg border px-2 py-2 text-left transition ${
                          clip && clipIdentityKey(clip) === clipIdentityKey(candidate)
                            ? 'border-primary/40 bg-primary/10'
                            : 'border-border bg-background/40 hover:border-secondary/40 hover:bg-secondary/10'
                        }`}
                      >
                        <video
                          src={getClipUrl(candidate, { cacheBust: candidate.created_at })}
                          className="h-10 w-16 rounded-md border border-border bg-black object-cover"
                          muted
                          playsInline
                          preload="metadata"
                        />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-foreground">{candidate.ui_title || candidate.name}</div>
                          <div className="truncate text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground">{resolveProjectId(candidate) ?? 'no-project'}</div>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <a
                href="/?tab=social"
                className="inline-flex items-center gap-2 rounded-xl border border-border bg-foreground/5 px-4 py-3 text-xs font-mono uppercase tracking-[0.16em]"
              >
                <ExternalLink className="h-4 w-4" />
                {t('socialComposePage.actions.dashboard')}
              </a>
              {controller.connectionMode === 'managed' && controller.connectUrl ? (
                <a
                  href={controller.connectUrl}
                  onClick={controller.handleManagedConnectOpen}
                  className="inline-flex items-center gap-2 rounded-xl border border-primary/40 bg-primary/15 px-4 py-3 text-xs font-mono uppercase tracking-[0.16em] text-primary"
                >
                  <Sparkles className="h-4 w-4" />
                  {t('socialComposePage.actions.connect')}
                </a>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.95fr_1.2fr]">
        <div className="space-y-6 xl:sticky xl:top-6 xl:self-start">
          <PreviewPanel
            activeContent={activeContent}
            clip={clip}
            previewUrl={previewUrl}
            selectedAccounts={selectedPlatformAccounts.filter((account) => controller.selectedAccountIds.includes(account.id))}
            selectedPlatform={controller.selectedPlatform}
          />
          <InsightsPanel activeContent={activeContent} selectedPlatform={controller.selectedPlatform} />
        </div>

        <div className="space-y-6">
          <EditorPanel
            activeContent={activeContent}
            controller={controller}
            platformAccounts={selectedPlatformAccounts}
          />
          <ActionPanel clip={clip} controller={controller} />
          <RecentJobsPanel jobs={controller.jobs} />
        </div>
      </section>
    </main>
  );
}

function PreviewPanel({
  activeContent,
  clip,
  previewUrl,
  selectedAccounts,
  selectedPlatform,
}: {
  activeContent: ShareDraftContent | null;
  clip: Clip | null;
  previewUrl: string | null;
  selectedAccounts: SocialAccount[];
  selectedPlatform: SocialPlatform;
}) {
  const { t } = useTranslation();

  return (
    <section className="glass-card border-white/10 p-5 sm:p-6 space-y-4">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.18em] text-accent">
        <Sparkles className="h-4 w-4" />
        {t('socialComposePage.preview.title')}
      </div>
      <div className="overflow-hidden rounded-2xl border border-border bg-background/80">
        {previewUrl ? (
          <video src={previewUrl} controls className="aspect-[9/16] max-h-[720px] w-full bg-black object-contain" />
        ) : (
          <div className="flex aspect-[9/16] items-center justify-center px-6 text-center text-sm text-muted-foreground">
            {t('socialComposePage.preview.noVideo')}
          </div>
        )}
      </div>

      {activeContent ? (
        <div className="rounded-2xl border border-secondary/20 bg-secondary/10 p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-foreground">{getPlatformLabel(selectedPlatform)}</div>
              <div className="text-xs text-muted-foreground">{t('socialComposePage.status.generated')}</div>
            </div>
            <div className="rounded-full border border-secondary/30 bg-secondary/15 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.18em] text-secondary">
              {selectedAccounts[0]?.name ?? t('socialComposePage.preview.account')}
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">{t('socialComposePage.preview.hook')}</div>
            <div className="text-lg font-black tracking-tight text-foreground">{activeContent.hook_text || activeContent.title}</div>
          </div>
          <div className="space-y-2">
            <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">{activeContent.title}</div>
            <p className="text-sm leading-7 text-foreground/90 whitespace-pre-wrap">{activeContent.text}</p>
          </div>
        </div>
      ) : null}

      {clip ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <InfoChip label={clip.name} />
          <InfoChip label={resolveProjectId(clip) ?? 'no-project'} />
        </div>
      ) : (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          {t('socialComposePage.clipPicker.choose')}
        </div>
      )}
    </section>
  );
}

function InsightsPanel({
  activeContent,
  selectedPlatform,
}: {
  activeContent: ShareDraftContent | null;
  selectedPlatform: SocialPlatform;
}) {
  const { t } = useTranslation();
  const content = activeContent ?? { title: '', text: '', hashtags: [], hook_text: '', cta_text: '' };
  const keywords = buildKeywordHints(content);
  const ctaText = content.cta_text || defaultCtaForPlatform(selectedPlatform);

  return (
    <section className="glass-card border-white/10 p-5 sm:p-6 space-y-4">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.18em] text-primary">
        <Wand2 className="h-4 w-4" />
        {t('socialComposePage.editor.title')}
      </div>
      <SignalCard label={t('socialComposePage.preview.hook')} value={content.hook_text || content.title || '...'} />
      <SignalCard label={t('socialComposePage.preview.cta')} value={ctaText} />
      <SignalCard label={t('socialComposePage.preview.hashtags')} value={content.hashtags.map((tag) => `#${tag}`).join(' ') || '...'} icon={<Hash className="h-4 w-4" />} />
      <SignalCard label={t('socialComposePage.preview.keywords')} value={keywords.join(' • ') || '...'} />
    </section>
  );
}

function EditorPanel({
  activeContent,
  controller,
  platformAccounts,
}: {
  activeContent: ShareDraftContent | null;
  controller: ReturnType<typeof useShareComposerController>;
  platformAccounts: SocialAccount[];
}) {
  const { t } = useTranslation();
  const ctaText = activeContent?.cta_text || defaultCtaForPlatform(controller.selectedPlatform);

  return (
    <section className="glass-card border-white/10 p-5 sm:p-6 space-y-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.18em] text-accent">
          <Send className="h-4 w-4" />
          {t('socialComposePage.editor.title')}
        </div>
        <button
          type="button"
          onClick={() => void controller.handleRefreshConnection()}
          className="inline-flex items-center gap-2 rounded-xl border border-border bg-foreground/5 px-3 py-2 text-[11px] font-mono uppercase tracking-[0.16em]"
        >
          {t('socialComposePage.actions.refresh')}
        </button>
      </div>

      {controller.error ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {controller.error}
        </div>
      ) : null}
      {controller.success ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4" />
          {controller.success}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {(['youtube_shorts', 'tiktok', 'instagram_reels', 'facebook_reels', 'x', 'linkedin'] as SocialPlatform[]).map((platform) => (
          <button
            key={platform}
            type="button"
            onClick={() => controller.setSelectedPlatform(platform)}
            className={`rounded-full border px-3 py-1.5 text-xs font-mono uppercase tracking-[0.14em] ${
              controller.selectedPlatform === platform
                ? 'border-primary/40 bg-primary/15 text-primary'
                : 'border-border bg-foreground/5 text-muted-foreground'
            }`}
          >
            {getPlatformLabel(platform)}
          </button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Field label={t('socialComposePage.editor.hook')}>
          <input
            value={activeContent?.hook_text ?? ''}
            onChange={(event) => controller.updateActiveContent({ hook_text: event.target.value })}
            className="w-full rounded-xl border border-border bg-background/70 px-4 py-3 text-sm text-foreground"
          />
        </Field>
        <Field label={t('socialComposePage.editor.cta')}>
          <input
            value={ctaText}
            onChange={(event) => controller.updateActiveContent({ cta_text: event.target.value })}
            className="w-full rounded-xl border border-border bg-background/70 px-4 py-3 text-sm text-foreground"
          />
        </Field>
      </div>

      <Field label={t('socialComposePage.editor.titleLabel')}>
        <input
          value={activeContent?.title ?? ''}
          onChange={(event) => controller.updateActiveContent({ title: event.target.value })}
          className="w-full rounded-xl border border-border bg-background/70 px-4 py-3 text-sm text-foreground"
        />
      </Field>

      <Field label={t('socialComposePage.editor.caption')}>
        <textarea
          rows={7}
          value={activeContent?.text ?? ''}
          onChange={(event) => controller.updateActiveContent({ text: event.target.value })}
          className="w-full rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm leading-7 text-foreground"
        />
      </Field>

      <Field label={t('socialComposePage.editor.hashtags')}>
        <input
          value={activeContent?.hashtags.join(', ') ?? ''}
          onChange={(event) => controller.updateActiveHashtags(event.target.value)}
          className="w-full rounded-xl border border-border bg-background/70 px-4 py-3 text-sm text-foreground"
        />
      </Field>

      <Field label={t('socialComposePage.editor.accounts')}>
        <div className="flex flex-wrap gap-2">
          {platformAccounts.length === 0 ? (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              {t('socialComposePage.editor.noAccounts')}
            </div>
          ) : platformAccounts.map((account) => (
            <label key={account.id} className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-foreground/5 px-3 py-2 text-xs">
              <input
                type="checkbox"
                checked={controller.selectedAccountIds.includes(account.id)}
                onChange={() => controller.toggleAccount(account.id)}
              />
              {account.name}
            </label>
          ))}
        </div>
      </Field>
    </section>
  );
}

function ActionPanel({
  clip,
  controller,
}: {
  clip: Clip | null;
  controller: ReturnType<typeof useShareComposerController>;
}) {
  const { t } = useTranslation();

  return (
    <section className="glass-card border-white/10 p-5 sm:p-6 space-y-4">
      <div className="grid gap-4 md:grid-cols-[1fr_auto_auto_auto] md:items-end">
        <Field label={t('socialComposePage.editor.schedule')}>
          <div className="relative">
            <CalendarClock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="datetime-local"
              value={controller.scheduleAt}
              onChange={(event) => controller.setScheduleAt(event.target.value)}
              className="w-full rounded-xl border border-border bg-background/70 py-3 pl-10 pr-4 text-sm text-foreground"
            />
          </div>
        </Field>
        <button
          type="button"
          onClick={() => void controller.submitPublish('now', false)}
          disabled={controller.publishing || !clip}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-primary/40 bg-primary/15 px-4 py-3 text-xs font-mono uppercase tracking-[0.16em] text-primary disabled:opacity-50"
        >
          {controller.publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          {t('socialComposePage.actions.publishNow')}
        </button>
        <button
          type="button"
          onClick={() => void controller.submitPublish('scheduled', false)}
          disabled={controller.publishing || !clip}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-secondary/40 bg-secondary/15 px-4 py-3 text-xs font-mono uppercase tracking-[0.16em] text-secondary disabled:opacity-50"
        >
          <CalendarClock className="h-4 w-4" />
          {t('socialComposePage.actions.schedule')}
        </button>
        <button
          type="button"
          onClick={() => void controller.submitPublish('now', true)}
          disabled={controller.publishing || !clip}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-border bg-foreground/5 px-4 py-3 text-xs font-mono uppercase tracking-[0.16em] disabled:opacity-50"
        >
          <Sparkles className="h-4 w-4" />
          {t('socialComposePage.actions.approval')}
        </button>
      </div>
      <div className="rounded-2xl border border-border bg-foreground/5 p-4 text-sm text-muted-foreground">
        {clip
          ? `${clip.name} · ${resolveProjectId(clip) ?? 'no-project'} · ${getPlatformLabel(controller.selectedPlatform)}`
          : t('socialComposePage.clipPicker.choose')}
      </div>
    </section>
  );
}

function RecentJobsPanel({ jobs }: { jobs: ReturnType<typeof useShareComposerController>['jobs'] }) {
  const { t } = useTranslation();

  return (
    <section className="glass-card border-white/10 p-5 sm:p-6 space-y-4">
      <div className="text-xs font-mono uppercase tracking-[0.18em] text-accent">{t('socialComposePage.status.recentJobs')}</div>
      {jobs.length === 0 ? (
        <div className="rounded-xl border border-border bg-foreground/5 px-4 py-3 text-sm text-muted-foreground">
          {t('socialComposePage.status.noJobs')}
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.slice(0, 5).map((job) => (
            <div key={job.id} className="rounded-xl border border-border bg-background/40 px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-foreground">{job.platform}</div>
                  <div className="text-xs text-muted-foreground">{job.state}</div>
                </div>
                <div className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">{job.mode}</div>
              </div>
              {job.timeline?.length ? (
                <div className="mt-3 space-y-1">
                  {job.timeline.slice(-2).map((item) => (
                    <div key={`${job.id}:${item.at}:${item.state}`} className="text-xs text-muted-foreground">
                      {item.state} · {item.message}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="block space-y-2">
      <span className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function SignalCard({
  icon,
  label,
  value,
}: {
  icon?: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-foreground/5 p-4 space-y-2">
      <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="text-sm leading-6 text-foreground/90">{value}</div>
    </div>
  );
}

function InfoChip({ label }: { label: string }) {
  return (
    <div className="rounded-full border border-border bg-foreground/5 px-3 py-2 text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
      {label}
    </div>
  );
}
