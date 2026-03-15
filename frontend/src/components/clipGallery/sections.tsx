import {
  AlertCircle,
  ArrowUpDown,
  CalendarClock,
  Download,
  Edit3,
  FolderKanban,
  RefreshCw,
  Share2,
  Trash2,
  Video,
  X,
} from 'lucide-react';

import type { Clip } from '../../types';
import type { ClipSortOrder } from './useClipGalleryController';
import { getClipUrl } from '../../utils/url';
import { IconButton } from '../ui/IconButton';
import { LazyVideo } from '../ui/LazyVideo';
import { Select } from '../ui/Select';
import { downloadMediaSource } from '../ui/protectedMedia';
import type { JSX } from 'react';

const DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

function formatCreatedAt(createdAt: number) {
  return DATE_FORMATTER.format(new Date(createdAt * 1000));
}

export function GalleryHeader({
  hasMore,
  loadedCount,
  pageSizeLimit,
  projectFilter,
  projectOptions,
  setProjectFilter,
  setSortOrder,
  sortOrder,
  totalCount,
  visibleCount,
}: {
  hasMore: boolean;
  loadedCount: number;
  pageSizeLimit: number;
  projectFilter: string;
  projectOptions: Array<{ label: string; value: string }>;
  setProjectFilter: (value: string) => void;
  setSortOrder: (value: ClipSortOrder) => void;
  sortOrder: ClipSortOrder;
  totalCount: number;
  visibleCount: number;
}) {
  return (
    <div className="relative z-10 glass-card p-5 border-primary/15 space-y-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-xl font-bold tracking-tighter flex items-center gap-2">
              <Video className="w-5 h-5 text-primary" aria-hidden="true" />
              CLIP LIBRARY
            </h2>
            <span className="rounded-full border border-primary/20 bg-primary/8 px-3 py-1 text-[11px] font-mono uppercase tracking-widest text-primary">
              {totalCount} Clips
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
            <span>{visibleCount} Visible</span>
            {hasMore && <span>Showing Newest {pageSizeLimit} Clips</span>}
            {!hasMore && loadedCount > 0 && <span>Workspace Indexed</span>}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 xl:min-w-[420px]">
          <ToolbarField
            ariaLabel="Project Filter"
            icon={<FolderKanban className="w-4 h-4 text-primary/60" aria-hidden="true" />}
            label="Project"
            options={projectOptions}
            value={projectFilter}
            onChange={setProjectFilter}
          />
          <ToolbarField
            ariaLabel="Sort Clips"
            icon={<ArrowUpDown className="w-4 h-4 text-primary/60" aria-hidden="true" />}
            label="Sort"
            options={[
              { label: 'Newest', value: 'newest' },
              { label: 'Oldest', value: 'oldest' },
            ]}
            value={sortOrder}
            onChange={(value) => setSortOrder(value as ClipSortOrder)}
          />
        </div>
      </div>
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
  return (
    <div className="h-40 glass-card flex items-center justify-center" aria-live="polite">
      <span className="animate-pulse text-xs font-mono text-muted-foreground uppercase tracking-widest">
        Indexing Clip Library...
      </span>
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
  return (
    <div role="alert" className="h-40 glass-card flex flex-col items-center justify-center gap-3 border-red-500/20">
      <div className="flex items-center gap-2 text-xs text-red-400 font-mono">
        <AlertCircle className="w-4 h-4" aria-hidden="true" />
        {errorMsg ?? 'Baglanti hatasi'}
      </div>
      <button
        onClick={onRetry}
        className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-xs font-mono uppercase transition-colors flex items-center gap-2"
        aria-label="Tekrar dene"
      >
        <RefreshCw className="w-3 h-3" aria-hidden="true" />
        Tekrar Dene
      </button>
    </div>
  );
}

export function EmptyState() {
  return (
    <div className="h-40 glass-card flex flex-col items-center justify-center text-muted-foreground border-dashed border-2">
      <div className="text-xs font-mono uppercase tracking-widest opacity-60">No clips generated yet...</div>
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
  if (clips.length === 0) {
    return (
      <div className="glass-card border-dashed border px-4 py-10 text-center text-xs font-mono uppercase tracking-widest text-muted-foreground">
        No clips match the current filters.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
  const clipUrl = getClipUrl(clip, { cacheBust: clip.created_at });

  return (
    <div className="glass-card group hover:border-primary/40 transition-all duration-500 overflow-hidden">
      <div className="aspect-[9/16] bg-black/60 relative overflow-hidden">
        <LazyVideo src={clipUrl} className="w-full h-full" />

        <div className="absolute inset-x-0 top-0 p-3 flex items-start justify-between gap-3">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-black/45 px-3 py-1 text-[11px] font-mono uppercase tracking-widest text-white/80 backdrop-blur-sm">
            <FolderKanban className="w-3.5 h-3.5 text-primary" aria-hidden="true" />
            <span className="truncate max-w-[150px]">{clip.project ?? 'legacy'}</span>
          </div>
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-mono uppercase tracking-widest backdrop-blur-sm ${
              clip.has_transcript
                ? 'border border-emerald-400/30 bg-emerald-500/15 text-emerald-100'
                : 'border border-amber-400/30 bg-amber-500/15 text-amber-100'
            }`}
          >
            {clip.has_transcript ? 'Transcript Ready' : 'Transcript Missing'}
          </span>
        </div>

        <div className="absolute inset-x-0 bottom-0 p-4 bg-gradient-to-t from-black via-black/75 to-transparent space-y-3">
          <div className="space-y-1 min-w-0">
            {clip.ui_title && (
              <div className="text-[11px] font-black text-accent-foreground/95 leading-tight truncate uppercase italic drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
                {clip.ui_title}
              </div>
            )}
            <div className="text-[12px] font-mono text-white/70 truncate uppercase">{clip.name}</div>
            <div className="inline-flex items-center gap-2 text-[11px] text-white/60">
              <CalendarClock className="w-3.5 h-3.5 text-primary/80" aria-hidden="true" />
              <span>{formatCreatedAt(clip.created_at)}</span>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <IconButton
              label="Subtitle Edit"
              icon={<Edit3 className="w-3.5 h-3.5" />}
              onClick={() => onEditClip?.(clip)}
              variant="primary"
            />
            <IconButton
              label="Download"
              icon={<Download className="w-3.5 h-3.5" />}
              onClick={() => void downloadMediaSource(clipUrl, clip.name)}
              variant="subtle"
            />
            <IconButton
              label="Share"
              icon={<Share2 className="w-3.5 h-3.5" />}
              onClick={() => onShareClip(clip)}
              variant="ghost"
            />
            <IconButton
              label="Delete"
              icon={<Trash2 className="w-3.5 h-3.5" />}
              onClick={() => onDeleteClip(clip)}
              variant="danger"
            />
          </div>
        </div>
      </div>
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

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm p-4 flex items-center justify-center">
      <div role="dialog" aria-modal="true" aria-labelledby="delete-clip-title" className="w-full max-w-md glass-card border-red-500/20 p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <h3 id="delete-clip-title" className="text-sm font-mono uppercase tracking-[0.2em] text-red-200 flex items-center gap-2">
              <Trash2 className="w-4 h-4" aria-hidden="true" />
              Delete Clip
            </h3>
            <p className="text-sm text-foreground">{clip.name}</p>
            <p className="text-[11px] font-mono uppercase tracking-widest text-muted-foreground">
              {clip.project ?? 'legacy'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="inline-flex items-center justify-center rounded-full min-w-[36px] min-h-[36px] bg-foreground/10 hover:bg-foreground/20 disabled:opacity-40"
            aria-label="Close delete modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">
          This removes the clip video, metadata, and raw backup if it exists. This action cannot be undone.
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
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-4 py-2 rounded-lg border border-red-500/40 bg-red-500/20 hover:bg-red-500/30 text-xs font-mono uppercase text-red-100 disabled:opacity-40"
          >
            {isDeleting ? 'Deleting...' : 'Delete Clip'}
          </button>
        </div>
      </div>
    </div>
  );
}
