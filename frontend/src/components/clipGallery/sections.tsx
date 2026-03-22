import {
  AlertCircle,
  ArrowUpDown,
  Download,
  Edit3,
  FolderKanban,
  RefreshCw,
  Share2,
  Trash2,
  Video,
  X,
} from 'lucide-react';

import type { Clip, ClipTranscriptStatus, OwnershipRecoveryProject } from '../../types';
import type { ClipSortOrder } from './useClipGalleryController';
import { formatDateTime, normalizeLocale } from '../../i18n';
import { getClipUrl } from '../../utils/url';
import { IconButton } from '../ui/IconButton';
import { LazyVideo } from '../ui/LazyVideo';
import { Select } from '../ui/Select';
import { downloadMediaSource } from '../ui/protectedMedia';
import { useState, type JSX, type KeyboardEvent, type MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';

function formatCreatedAt(createdAt: number, locale: 'en' | 'tr') {
  return formatDateTime(createdAt * 1000, locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function formatDurationLabel(duration: number | null | undefined) {
  if (typeof duration !== 'number' || !Number.isFinite(duration) || duration <= 0) {
    return null;
  }

  const totalSeconds = Math.round(duration);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }

  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function formatOwnershipCreatedAt(createdAt: string, locale: 'en' | 'tr') {
  return formatDateTime(createdAt, locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function formatSubjectHash(subjectHash: string | null, unknownLabel: string) {
  if (!subjectHash) {
    return unknownLabel;
  }
  return `${subjectHash.slice(0, 8)}...${subjectHash.slice(-4)}`;
}

function resolveClipTranscriptBadge(
  clip: Clip,
  t: (key: string) => string,
) {
  const transcriptStatus: ClipTranscriptStatus = clip.transcript_status ?? (clip.has_transcript ? 'ready' : 'needs_recovery');

  if (transcriptStatus === 'ready') {
    return {
      className: 'border border-emerald-400/30 bg-emerald-500/15 text-emerald-100',
      label: t('clipGallery.transcript.ready'),
    };
  }

  if (transcriptStatus === 'project_pending' || transcriptStatus === 'recovering') {
    return {
      className: 'border border-sky-400/30 bg-sky-500/15 text-sky-100',
      label: t('clipGallery.transcript.processing'),
    };
  }

  return {
    className: 'border border-amber-400/30 bg-amber-500/15 text-amber-100',
    label: t('clipGallery.transcript.recoveryNeeded'),
  };
}

export function GalleryHeader({
  authMode,
  currentSubjectHash,
  hasMore,
  handleClaimProject,
  isClaimingProjectId,
  loadedCount,
  ownershipNotice,
  ownershipNoticeTone,
  pageSizeLimit,
  productionInProgress,
  projectFilter,
  projectOptions,
  reclaimableProjects,
  setProjectFilter,
  setSortOrder,
  sortOrder,
  staleRefreshWarning,
  totalCount,
  visibleCount,
}: {
  authMode: 'clerk_jwt' | 'static_token' | null;
  currentSubjectHash: string | null;
  hasMore: boolean;
  handleClaimProject: (projectId: string) => void;
  isClaimingProjectId: string | null;
  loadedCount: number;
  ownershipNotice: string | null;
  ownershipNoticeTone: 'danger' | 'info';
  pageSizeLimit: number;
  productionInProgress: boolean;
  projectFilter: string;
  projectOptions: Array<{ label: string; value: string }>;
  reclaimableProjects: OwnershipRecoveryProject[];
  setProjectFilter: (value: string) => void;
  setSortOrder: (value: ClipSortOrder) => void;
  sortOrder: ClipSortOrder;
  staleRefreshWarning: string | null;
  totalCount: number;
  visibleCount: number;
}) {
  const { t } = useTranslation();
  const summaryBadges = [
    t('clipGallery.visible', { count: visibleCount }),
    hasMore ? t('clipGallery.newest', { count: pageSizeLimit }) : null,
    !hasMore && loadedCount > 0 ? t('clipGallery.indexed') : null,
    productionInProgress ? t('clipGallery.production') : null,
  ].filter((value): value is string => Boolean(value));

  return (
    <div className="relative z-10 glass-card p-5 border-primary/15 space-y-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <GallerySummary
          authMode={authMode}
          currentSubjectHash={currentSubjectHash}
          productionInProgress={productionInProgress}
          staleRefreshWarning={staleRefreshWarning}
          summaryBadges={summaryBadges}
          totalCount={totalCount}
        />
        <GalleryToolbar
          projectFilter={projectFilter}
          projectOptions={projectOptions}
          setProjectFilter={setProjectFilter}
          setSortOrder={setSortOrder}
          sortOrder={sortOrder}
        />
      </div>
      <OwnershipRecoveryPanel
        currentSubjectHash={currentSubjectHash}
        handleClaimProject={handleClaimProject}
        isClaimingProjectId={isClaimingProjectId}
        ownershipNotice={ownershipNotice}
        ownershipNoticeTone={ownershipNoticeTone}
        reclaimableProjects={reclaimableProjects}
      />
    </div>
  );
}

function GallerySummary({
  authMode,
  currentSubjectHash,
  productionInProgress,
  staleRefreshWarning,
  summaryBadges,
  totalCount,
}: {
  authMode: 'clerk_jwt' | 'static_token' | null;
  currentSubjectHash: string | null;
  productionInProgress: boolean;
  staleRefreshWarning: string | null;
  summaryBadges: string[];
  totalCount: number;
}) {
  const { t } = useTranslation();

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-bold tracking-tighter flex items-center gap-2">
          <Video className="w-5 h-5 text-primary" aria-hidden="true" />
          {t('clipGallery.title')}
        </h2>
        <span className="rounded-full border border-primary/20 bg-primary/8 px-3 py-1 text-[11px] font-mono uppercase tracking-widest text-primary">
          {t('clipGallery.count', { count: totalCount })}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
        {summaryBadges.map((badge) => <span key={badge}>{badge}</span>)}
      </div>
      <p className="text-[11px] font-mono uppercase tracking-widest text-sky-100/80">
        {t('clipGallery.account', { hash: formatSubjectHash(currentSubjectHash, t('clipGallery.date.unknownSubject')) })} {authMode ? `| ${authMode === 'clerk_jwt' ? t('clipGallery.authMode.clerk') : t('clipGallery.authMode.staticToken')}` : ''}
      </p>
      {productionInProgress && (
        <p className="text-[11px] font-mono uppercase tracking-widest text-emerald-200/80">
          {t('clipGallery.newClipsAppear')}
        </p>
      )}
      <p className="text-[11px] font-mono uppercase tracking-widest text-amber-200/80">
        {t('clipGallery.ownerScoped')}
      </p>
      {staleRefreshWarning && (
        <p className="text-[11px] font-mono uppercase tracking-widest text-red-200/80">
          {staleRefreshWarning}
        </p>
      )}
    </div>
  );
}

function OwnershipRecoveryPanel({
  currentSubjectHash,
  handleClaimProject,
  isClaimingProjectId,
  ownershipNotice,
  ownershipNoticeTone,
  reclaimableProjects,
}: {
  currentSubjectHash: string | null;
  handleClaimProject: (projectId: string) => void;
  isClaimingProjectId: string | null;
  ownershipNotice: string | null;
  ownershipNoticeTone: 'danger' | 'info';
  reclaimableProjects: OwnershipRecoveryProject[];
}) {
  const { t, i18n } = useTranslation();
  const locale = normalizeLocale(i18n.language);

  if (!ownershipNotice && reclaimableProjects.length === 0) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-amber-300/20 bg-black/20 px-4 py-4 space-y-3">
      {ownershipNotice && (
        <p
          className={`text-[11px] font-mono uppercase tracking-widest ${
            ownershipNoticeTone === 'danger' ? 'text-red-200/85' : 'text-emerald-200/85'
          }`}
        >
          {ownershipNotice}
        </p>
      )}
      {reclaimableProjects.length > 0 && (
        <>
          <p className="text-[11px] font-mono uppercase tracking-widest text-amber-100/85">
            {t('clipGallery.ownership.projectsBelongToOtherIdentity', {
              count: reclaimableProjects.length,
              hash: formatSubjectHash(currentSubjectHash, t('clipGallery.date.unknownSubject')),
            })}
          </p>
          <div className="grid gap-3">
            {reclaimableProjects.map((project) => {
              const isClaiming = isClaimingProjectId === project.project_id;
              return (
                <div
                  key={project.project_id}
                  className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 lg:flex-row lg:items-center lg:justify-between"
                >
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-foreground">{project.project_id}</p>
                    <p className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
                      {t('clipGallery.ownership.ownerLine', {
                        count: project.clip_count,
                        createdAt: formatOwnershipCreatedAt(project.created_at, locale),
                        owner: formatSubjectHash(project.owner_subject_hash, t('clipGallery.date.unknownSubject')),
                      })}
                    </p>
                    {project.latest_clip_name && (
                      <p className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
                        {t('clipGallery.ownership.latestClip', { name: project.latest_clip_name })}
                      </p>
                    )}
                  </div>
                  <button
                    className="rounded-full border border-primary/30 bg-primary/10 px-4 py-2 text-[11px] font-mono uppercase tracking-widest text-primary transition hover:border-primary/60 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={Boolean(isClaimingProjectId)}
                    onClick={() => handleClaimProject(project.project_id)}
                    type="button"
                  >
                    {isClaiming ? t('clipGallery.ownership.claiming') : t('clipGallery.ownership.claim')}
                  </button>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function GalleryToolbar({
  projectFilter,
  projectOptions,
  setProjectFilter,
  setSortOrder,
  sortOrder,
}: {
  projectFilter: string;
  projectOptions: Array<{ label: string; value: string }>;
  setProjectFilter: (value: string) => void;
  setSortOrder: (value: ClipSortOrder) => void;
  sortOrder: ClipSortOrder;
}) {
  const { t } = useTranslation();

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 xl:min-w-[420px]">
      <ToolbarField
        ariaLabel="Project Filter"
        icon={<FolderKanban className="w-4 h-4 text-primary/60" aria-hidden="true" />}
        label={t('clipGallery.toolbar.project')}
        options={projectOptions}
        value={projectFilter}
        onChange={setProjectFilter}
      />
      <ToolbarField
        ariaLabel="Sort Clips"
        icon={<ArrowUpDown className="w-4 h-4 text-primary/60" aria-hidden="true" />}
        label={t('clipGallery.toolbar.sort')}
        options={[
          { label: t('clipGallery.sort.newest'), value: 'newest' },
          { label: t('clipGallery.sort.oldest'), value: 'oldest' },
        ]}
        value={sortOrder}
        onChange={(value) => setSortOrder(value as ClipSortOrder)}
      />
    </div>
  );
}

function ToolbarField({
  ariaLabel,
  icon,
  label,
  options,
  onChange,
  value,
}: {
  ariaLabel: string;
  icon: JSX.Element;
  label: string;
  options: Array<{ label: string; value: string }>;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <Select
      ariaLabel={ariaLabel}
      className="text-sm"
      icon={icon}
      label={label}
      onChange={onChange}
      options={options}
      value={value}
    />
  );
}

export function LoadingState() {
  const { t } = useTranslation();

  return (
    <div className="h-40 glass-card flex items-center justify-center" aria-live="polite">
      <span className="animate-pulse text-xs font-mono text-muted-foreground uppercase tracking-widest">
        {t('clipGallery.states.loading')}
      </span>
    </div>
  );
}

export function ProcessingState() {
  const { t } = useTranslation();

  return (
    <div className="glass-card flex flex-col items-center justify-center gap-3 px-6 py-10 text-center" aria-live="polite">
      <span className="animate-pulse text-xs font-mono uppercase tracking-widest text-primary/80">
        {t('clipGallery.states.renderInProgress')}
      </span>
      <p className="max-w-xl text-sm leading-6 text-muted-foreground">
        {t('clipGallery.states.renderInProgressHint')}
      </p>
    </div>
  );
}

export function ErrorState({
  errorMsg,
  onRetry,
}: {
  errorMsg: string | null;
  onRetry: () => void;
}) {
  const { t } = useTranslation();

  return (
    <div role="alert" className="h-40 glass-card flex flex-col items-center justify-center gap-3 border-red-500/20">
      <div className="flex items-center gap-2 text-xs text-red-400 font-mono">
        <AlertCircle className="w-4 h-4" aria-hidden="true" />
        {errorMsg ?? t('clipGallery.states.refreshFailed')}
      </div>
      <button
        onClick={onRetry}
        className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-xs font-mono uppercase transition-colors flex items-center gap-2"
        aria-label={t('common.actions.retry')}
      >
        <RefreshCw className="w-3 h-3" aria-hidden="true" />
        {t('common.actions.retry')}
      </button>
    </div>
  );
}

export function AuthBlockedState({
  errorMsg,
  onRetry,
}: {
  errorMsg: string | null;
  onRetry: () => void;
}) {
  const { t } = useTranslation();

  return (
    <div role="status" className="glass-card flex flex-col items-center justify-center gap-3 border-amber-500/20 px-6 py-10 text-center">
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-amber-100">
        <AlertCircle className="w-4 h-4" aria-hidden="true" />
        {t('clipGallery.title')} {t('subtitleEditor.transcript.accessPending')}
      </div>
      <p className="max-w-xl text-sm leading-6 text-amber-50/90">
        {errorMsg ?? t('clipGallery.states.backendUnavailable')}
      </p>
      <button
        onClick={onRetry}
        className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-xs font-mono uppercase transition-colors flex items-center gap-2"
        aria-label={t('clipGallery.actions.retryLibrary')}
      >
        <RefreshCw className="w-3 h-3" aria-hidden="true" />
        {t('common.actions.retry')}
      </button>
    </div>
  );
}

export function EmptyState() {
  const { t } = useTranslation();

  return (
    <div className="h-40 glass-card flex flex-col items-center justify-center text-muted-foreground border-dashed border-2 text-center px-4 gap-2">
      <div className="text-xs font-mono uppercase tracking-widest opacity-70">{t('clipGallery.states.empty')}</div>
      <p className="text-[11px] leading-5 opacity-80 max-w-xl">
        {t('clipGallery.states.emptyHint')}
      </p>
    </div>
  );
}

export function ReadyState({
  clips,
  onDeleteClip,
  onEditClip,
  onShareClip,
}: {
  clips: Clip[];
  onDeleteClip: (clip: Clip) => void;
  onEditClip?: (clip: Clip) => void;
  onShareClip: (clip: Clip) => void;
}) {
  const { t } = useTranslation();
  if (clips.length === 0) {
    return (
      <div className="glass-card border-dashed border px-4 py-10 text-center text-xs font-mono uppercase tracking-widest text-muted-foreground">
        {t('clipGallery.states.empty')}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(228px,1fr))] items-start gap-3 sm:gap-4">
      {clips.map((clip) => (
        <ClipCard
          key={`${clip.project ?? 'legacy'}:${clip.name}`}
          clip={clip}
          onDeleteClip={onDeleteClip}
          onEditClip={onEditClip}
          onShareClip={onShareClip}
        />
      ))}
    </div>
  );
}

function ClipCard({
  clip,
  onDeleteClip,
  onEditClip,
  onShareClip,
}: {
  clip: Clip;
  onDeleteClip: (clip: Clip) => void;
  onEditClip?: (clip: Clip) => void;
  onShareClip: (clip: Clip) => void;
}) {
  const { t, i18n } = useTranslation();
  const locale = normalizeLocale(i18n.language);
  const [isFlipped, setIsFlipped] = useState(false);
  const clipUrl = getClipUrl(clip, { cacheBust: clip.created_at });
  const transcriptBadge = resolveClipTranscriptBadge(clip, t);
  const durationLabel = formatDurationLabel(clip.duration);
  const detailButtonLabel = isFlipped
    ? t('clipGallery.actions.hideDetails', { name: clip.name })
    : t('clipGallery.actions.showDetails', { name: clip.name });

  const toggleFlip = () => {
    setIsFlipped((current) => !current);
  };

  const handleCardKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }

    event.preventDefault();
    toggleFlip();
  };

  const stopCardFlip = (event: MouseEvent<HTMLElement>) => {
    event.stopPropagation();
  };

  return (
    <div
      aria-label={detailButtonLabel}
      aria-pressed={isFlipped}
      className="glass-card group w-full cursor-pointer overflow-hidden transition-all duration-500 hover:border-primary/40"
      onClick={toggleFlip}
      onKeyDown={handleCardKeyDown}
      role="button"
      tabIndex={0}
    >
      <div className="relative aspect-[9/16] overflow-hidden [perspective:1400px]">
        <div
          className="relative h-full w-full transition-transform duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{ transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)', transformStyle: 'preserve-3d' }}
        >
          <div
            aria-hidden={isFlipped}
            className="absolute inset-0 bg-black/60"
            style={{ backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden' }}
          >
            <LazyVideo src={clipUrl} className="h-full w-full" />

            <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-black/15" />
            <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-end p-3">
              <div className="inline-flex items-center rounded-full border border-white/12 bg-black/35 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.18em] text-white/70 backdrop-blur-sm">
                {t('clipGallery.actions.details')}
              </div>
            </div>
          </div>

          <div
            aria-hidden={!isFlipped}
            className="absolute inset-0 flex h-full flex-col bg-[radial-gradient(circle_at_top,rgba(0,242,255,0.16),transparent_45%),linear-gradient(180deg,rgba(7,10,14,0.96),rgba(4,6,9,0.98))] p-3"
            style={{ backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-1">
                <div className="text-[10px] font-mono uppercase tracking-[0.24em] text-primary/75">{t('clipGallery.title')}</div>
                <div className="line-clamp-2 text-sm font-semibold uppercase leading-tight text-foreground">
                  {clip.ui_title || clip.name.replace('.mp4', '')}
                </div>
              </div>
              <button
                aria-label={t('clipGallery.actions.hideDetails', { name: clip.name })}
                className="inline-flex min-h-[34px] min-w-[34px] items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/75 transition hover:bg-white/10 hover:text-white"
                onClick={(event) => {
                  stopCardFlip(event);
                  setIsFlipped(false);
                }}
                type="button"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <div className="mt-3 grid min-h-0 flex-1 grid-rows-[auto_auto_1fr_auto] gap-3">
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono uppercase tracking-widest text-white/75">
                <DetailPill label={t('clipGallery.detail.project')} value={clip.project ?? t('clipGallery.legacyProject')} />
                <DetailPill label={t('clipGallery.detail.transcript')} value={transcriptBadge.label} />
                <DetailPill className="col-span-2" label={t('clipGallery.detail.file')} value={clip.name} />
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono uppercase tracking-widest text-white/75">
                <DetailPill label={t('clipGallery.detail.created')} value={formatCreatedAt(clip.created_at, locale)} />
                <DetailPill label={t('clipGallery.detail.duration')} value={durationLabel ?? t('clipGallery.detail.unknown')} />
              </div>

              <div className="grid min-h-0 grid-cols-2 gap-2 text-[11px] font-mono uppercase tracking-widest text-white/75">
                {clip.ui_title ? (
                  <DetailPill
                    className="col-span-2"
                    label={t('clipGallery.detail.title')}
                    value={clip.ui_title}
                  />
                ) : (
                  <DetailPill
                    className="col-span-2"
                    label={t('clipGallery.detail.title')}
                    value={clip.name.replace('.mp4', '')}
                  />
                )}
              </div>

              <div className="grid grid-cols-2 gap-2" onClick={stopCardFlip}>
                <IconButton
                  label={t('clipGallery.actions.subtitleEdit')}
                  icon={<Edit3 className="w-3.5 h-3.5" />}
                  onClick={() => onEditClip?.(clip)}
                  variant="primary"
                />
                <IconButton
                  label={t('common.actions.download')}
                  icon={<Download className="w-3.5 h-3.5" />}
                  onClick={() => void downloadMediaSource(clipUrl, clip.name)}
                  variant="subtle"
                />
                <IconButton
                  label={t('common.actions.share')}
                  icon={<Share2 className="w-3.5 h-3.5" />}
                  onClick={() => onShareClip(clip)}
                  variant="ghost"
                />
                <IconButton
                  label={t('common.actions.delete')}
                  icon={<Trash2 className="w-3.5 h-3.5" />}
                  onClick={() => onDeleteClip(clip)}
                  variant="danger"
                />
              </div>
            </div>

            <div className="mt-3 rounded-2xl border border-white/10 bg-black/25 px-3 py-2 text-[10px] font-mono uppercase tracking-[0.18em] text-white/55">
              {t('common.actions.back')}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailPill({
  className,
  label,
  value,
}: {
  className?: string;
  label: string;
  value: string;
}) {
  return (
    <div className={`rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2 ${className ?? ''}`}>
      <div className="text-[9px] text-primary/70">{label}</div>
      <div className="mt-1 truncate text-[11px] text-white/88">{value}</div>
    </div>
  );
}

export function DeleteClipModal({
  clip,
  error,
  isDeleting,
  onClose,
  onConfirm,
}: {
  clip: Clip | null;
  error: string | null;
  isDeleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  if (!clip) {
    return null;
  }

  const { t } = useTranslation();

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm p-4 flex items-center justify-center">
      <div role="dialog" aria-modal="true" aria-labelledby="delete-clip-title" className="w-full max-w-md glass-card border-red-500/20 p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <h3 id="delete-clip-title" className="text-sm font-mono uppercase tracking-[0.2em] text-red-200 flex items-center gap-2">
              <Trash2 className="w-4 h-4" aria-hidden="true" />
              {t('clipGallery.actions.deleteConfirm')}
            </h3>
            <p className="text-sm text-foreground">{clip.name}</p>
            <p className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
              {clip.project ?? t('clipGallery.legacyProject')}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="inline-flex items-center justify-center rounded-full min-w-[36px] min-h-[36px] bg-foreground/10 hover:bg-foreground/20 disabled:opacity-40"
            aria-label={t('clipGallery.actions.closeDeleteModal')}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">
          {t('clipGallery.deleteModal.description')}
        </div>

        {error && (
          <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="px-4 py-2 rounded-lg border border-border bg-foreground/10 hover:bg-foreground/20 text-xs font-mono uppercase disabled:opacity-40"
          >
            {t('common.actions.cancel')}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-4 py-2 rounded-lg border border-red-500/40 bg-red-500/20 hover:bg-red-500/30 text-xs font-mono uppercase text-red-100 disabled:opacity-40"
          >
            {isDeleting ? t('common.labels.loading') : t('clipGallery.actions.deleteConfirm')}
          </button>
        </div>
      </div>
    </div>
  );
}
