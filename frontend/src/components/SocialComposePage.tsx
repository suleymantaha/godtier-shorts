import {
  AlertCircle,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Hash,
  Loader2,
  Send,
  Sparkles,
  Wand2,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';

import { clipsApi } from '../api/client';
import { useResolvedMediaState } from './ui/protectedMedia';
import type { Clip, ShareDraftContent, SocialAccount, SocialPlatform } from '../types';
import { getClipUrl } from '../utils/url';
import { buildSocialComposeUrl, getPlatformLabel, resolveProjectId } from './shareComposer/helpers';
import { useShareComposerController } from './shareComposer/useShareComposerController';

const THUMBNAIL_CACHE = new Map<string, string | null>();

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

function defaultScheduleDate(now = Date.now()): Date {
  return new Date(now + 60 * 60 * 1000);
}

function parseScheduleAt(value: string): Date | null {
  if (!value) {
    return null;
  }

  const [datePart, timePart] = value.split('T');
  if (!datePart || !timePart) {
    return null;
  }

  const [year, month, day] = datePart.split('-').map(Number);
  const [hours, minutes] = timePart.split(':').map(Number);
  if (
    !Number.isFinite(year)
    || !Number.isFinite(month)
    || !Number.isFinite(day)
    || !Number.isFinite(hours)
    || !Number.isFinite(minutes)
  ) {
    return null;
  }

  return new Date(year, month - 1, day, hours, minutes, 0, 0);
}

function formatScheduleAt(value: string, locale: string): string {
  const parsed = parseScheduleAt(value);
  if (!parsed) {
    return value;
  }

  return new Intl.DateTimeFormat(locale, {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(parsed);
}

function toScheduleAtValue(date: Date): string {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hours = `${date.getHours()}`.padStart(2, '0');
  const minutes = `${date.getMinutes()}`.padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1, 0, 0, 0, 0);
}

function buildCalendarCells(displayMonth: Date): Array<Date | null> {
  const firstDay = new Date(displayMonth.getFullYear(), displayMonth.getMonth(), 1);
  const firstWeekday = firstDay.getDay();
  const daysInMonth = new Date(displayMonth.getFullYear(), displayMonth.getMonth() + 1, 0).getDate();
  const cells: Array<Date | null> = [];

  for (let index = 0; index < firstWeekday; index += 1) {
    cells.push(null);
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push(new Date(displayMonth.getFullYear(), displayMonth.getMonth(), day));
  }

  while (cells.length % 7 !== 0) {
    cells.push(null);
  }

  return cells;
}

function monthLabel(date: Date, locale: string): string {
  return new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(date);
}

function weekdayLabels(locale: string): string[] {
  const base = new Date(2024, 0, 7);
  return Array.from({ length: 7 }, (_, index) =>
    new Intl.DateTimeFormat(locale, { weekday: 'short' }).format(new Date(base.getTime() + index * 24 * 60 * 60 * 1000)),
  );
}

function isSameDay(left: Date | null, right: Date | null): boolean {
  if (!left || !right) {
    return false;
  }

  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
}

function useVideoThumbnail(src?: string): string | null | undefined {
  const [thumbnailState, setThumbnailState] = useState<{ src: string; value: string | null } | null>(null);
  const cachedThumbnail = src ? THUMBNAIL_CACHE.get(src) : undefined;

  useEffect(() => {
    if (!src || cachedThumbnail !== undefined) {
      return;
    }

    let cancelled = false;
    const video = document.createElement('video');
    video.src = src;
    video.muted = true;
    video.playsInline = true;
    video.preload = 'metadata';

    const finalize = (value: string | null) => {
      if (cancelled) {
        return;
      }
      THUMBNAIL_CACHE.set(src, value);
      setThumbnailState({ src, value });
    };

    const capture = () => {
      if (!video.videoWidth || !video.videoHeight) {
        finalize(null);
        return;
      }

      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext('2d');
      if (!context) {
        finalize(null);
        return;
      }

      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      finalize(canvas.toDataURL('image/jpeg', 0.78));
    };

    const handleLoadedData = () => {
      const duration = Number.isFinite(video.duration) && video.duration > 0
        ? Math.min(Math.max(video.duration * 0.12, 0.12), 1.4)
        : 0;

      if (duration <= 0.12) {
        capture();
        return;
      }

      const handleSeeked = () => {
        video.removeEventListener('seeked', handleSeeked);
        capture();
      };

      video.addEventListener('seeked', handleSeeked);
      try {
        video.currentTime = duration;
      } catch {
        video.removeEventListener('seeked', handleSeeked);
        capture();
      }
    };

    const handleError = () => finalize(null);

    video.addEventListener('loadeddata', handleLoadedData, { once: true });
    video.addEventListener('error', handleError, { once: true });
    video.load();

    return () => {
      cancelled = true;
      video.pause();
      video.removeAttribute('src');
      video.load();
      video.removeEventListener('error', handleError);
      video.removeEventListener('loadeddata', handleLoadedData);
    };
  }, [cachedThumbnail, src]);

  if (!src) {
    return undefined;
  }

  if (cachedThumbnail !== undefined) {
    return cachedThumbnail;
  }

  return thumbnailState?.src === src ? thumbnailState.value : undefined;
}

function useFloatingPanelStyle(anchorRef: RefObject<HTMLElement | null>, open: boolean, width?: number): CSSProperties | null {
  const [style, setStyle] = useState<CSSProperties | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    const updatePosition = () => {
      const anchor = anchorRef.current;
      if (!anchor) {
        return;
      }

      const rect = anchor.getBoundingClientRect();
      const panelWidth = Math.min(width ?? rect.width, window.innerWidth - 32);
      const left = Math.max(16, Math.min(rect.left, window.innerWidth - panelWidth - 16));
      const availableBelow = window.innerHeight - rect.bottom - 16;
      const availableAbove = rect.top - 16;
      const renderAbove = availableBelow < 260 && availableAbove > availableBelow;

      setStyle(renderAbove
        ? {
          bottom: window.innerHeight - rect.top + 10,
          left,
          maxHeight: Math.max(180, availableAbove - 12),
          position: 'fixed',
          width: panelWidth,
          zIndex: 140,
        }
        : {
          left,
          maxHeight: Math.max(180, availableBelow - 12),
          position: 'fixed',
          top: rect.bottom + 10,
          width: panelWidth,
          zIndex: 140,
        });
    };

    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);

    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [anchorRef, open, width]);

  return open ? style : null;
}

function FloatingPanel({
  anchorRef,
  children,
  onClose,
  open,
  width,
}: {
  anchorRef: RefObject<HTMLElement | null>;
  children: ReactNode;
  onClose: () => void;
  open: boolean;
  width?: number;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const style = useFloatingPanelStyle(anchorRef, open, width);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) {
        return;
      }

      if (anchorRef.current?.contains(target) || panelRef.current?.contains(target)) {
        return;
      }

      onClose();
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handlePointerDown, true);
    window.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown, true);
      window.removeEventListener('keydown', handleEscape);
    };
  }, [anchorRef, onClose, open]);

  if (!open || !style) {
    return null;
  }

  return createPortal(
    <div ref={panelRef} style={style} className="glass-card overflow-hidden border-white/10 shadow-[0_24px_70px_rgba(0,0,0,0.45)]">
      {children}
    </div>,
    document.body,
  );
}

function ClipThumbnail({
  clip,
  className,
}: {
  className?: string;
  clip: Clip;
}) {
  const src = getClipUrl(clip, { cacheBust: clip.created_at });
  const { resolvedSrc } = useResolvedMediaState(src);
  const thumbnail = useVideoThumbnail(resolvedSrc);

  if (thumbnail) {
    return <img src={thumbnail} alt="" className={className} />;
  }

  return (
    <div className={`${className} flex items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(0,242,255,0.16),_transparent_48%),linear-gradient(180deg,_rgba(18,18,24,0.96),_rgba(8,8,12,0.98))] text-[10px] font-mono uppercase tracking-[0.18em] text-white/65`}>
      {clip.ui_title?.slice(0, 2) ?? clip.name.slice(0, 2)}
    </div>
  );
}

function ProtectedPreviewVideo({ clip }: { clip: Clip | null }) {
  const { t } = useTranslation();
  const src = clip ? getClipUrl(clip, { cacheBust: clip.created_at }) : undefined;
  const { error, resolvedSrc } = useResolvedMediaState(src);

  if (!clip) {
    return (
      <div className="flex aspect-[9/16] items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(0,242,255,0.12),_transparent_40%),linear-gradient(180deg,_rgba(10,10,16,0.96),_rgba(3,3,6,0.98))] px-8 text-center">
        <div className="space-y-3">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-secondary/30 bg-secondary/12">
            <Sparkles className="h-6 w-6 text-secondary" />
          </div>
          <div className="text-sm font-semibold text-foreground">{t('socialComposePage.preview.emptyTitle')}</div>
          <p className="max-w-sm text-sm leading-6 text-muted-foreground">{t('socialComposePage.preview.emptyBody')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex aspect-[9/16] items-center justify-center bg-black/60 px-8 text-center text-sm text-red-200">
        {t('socialComposePage.preview.unavailable')}
      </div>
    );
  }

  if (!resolvedSrc) {
    return (
      <div className="flex aspect-[9/16] items-center justify-center bg-black/60">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('socialComposePage.preview.loading')}
        </div>
      </div>
    );
  }

  return <video src={resolvedSrc} controls className="aspect-[9/16] max-h-[720px] w-full bg-black object-contain" />;
}

function ClipPicker({
  clip,
  clipOptions,
  loading,
  error,
  onClear,
  onSelect,
}: {
  clip: Clip | null;
  clipOptions: Clip[];
  error: string | null;
  loading: boolean;
  onClear: () => void;
  onSelect: (clip: Clip) => void;
}) {
  const { t } = useTranslation();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-2">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-3 rounded-2xl border border-border bg-background/70 px-3 py-3 text-left transition hover:border-primary/35"
        aria-expanded={open}
        aria-label={t('socialComposePage.clipPicker.label')}
      >
        {clip ? (
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <ClipThumbnail clip={clip} className="h-12 w-20 shrink-0 rounded-lg border border-white/10 object-cover" />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-foreground" title={clip.ui_title || clip.name}>
                {clip.ui_title || clip.name}
              </div>
              <div className="truncate text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground" title={resolveProjectId(clip) ?? 'no-project'}>
                {resolveProjectId(clip) ?? 'no-project'}
              </div>
            </div>
          </div>
        ) : (
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-foreground">{t('socialComposePage.clipPicker.choose')}</div>
            <div className="text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground">{t('socialComposePage.clipPicker.label')}</div>
          </div>
        )}
        <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180 text-primary' : ''}`} />
      </button>

      <FloatingPanel anchorRef={triggerRef} open={open} onClose={() => setOpen(false)}>
        <div role="listbox" aria-label={t('socialComposePage.clipPicker.label')} className="max-h-[22rem] overflow-y-auto p-2">
          <button
            type="button"
            onClick={() => {
              onClear();
              setOpen(false);
            }}
            disabled={!clip}
            className="mb-2 flex w-full items-center justify-center rounded-xl border border-dashed border-white/15 bg-white/[0.03] px-3 py-2 text-xs font-mono uppercase tracking-[0.18em] text-muted-foreground transition hover:border-accent/45 hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t('socialComposePage.actions.clearSelection')}
          </button>
          {loading ? (
            <div className="flex items-center gap-2 px-3 py-3 text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {t('socialComposePage.clipPicker.loading')}
            </div>
          ) : error ? (
            <div className="px-3 py-3 text-sm text-red-300">{error}</div>
          ) : clipOptions.length === 0 ? (
            <div className="px-3 py-3 text-sm text-muted-foreground">{t('socialComposePage.clipPicker.empty')}</div>
          ) : (
            clipOptions.map((candidate) => {
              const isSelected = clip ? clipIdentityKey(clip) === clipIdentityKey(candidate) : false;
              return (
                <button
                  key={clipIdentityKey(candidate)}
                  type="button"
                  onClick={() => {
                    onSelect(candidate);
                    setOpen(false);
                  }}
                  className={`mb-2 flex w-full items-center gap-3 rounded-xl border px-2 py-2 text-left transition ${
                    isSelected
                      ? 'border-primary/40 bg-primary/10'
                      : 'border-white/10 bg-background/35 hover:border-secondary/35 hover:bg-secondary/10'
                  }`}
                >
                  <ClipThumbnail clip={candidate} className="h-12 w-20 shrink-0 rounded-lg border border-white/10 object-cover" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-foreground" title={candidate.ui_title || candidate.name}>
                      {candidate.ui_title || candidate.name}
                    </div>
                    <div className="truncate text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground" title={resolveProjectId(candidate) ?? 'no-project'}>
                      {resolveProjectId(candidate) ?? 'no-project'}
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </FloatingPanel>
    </div>
  );
}

function DateTimePicker({
  onChange,
  value,
}: {
  onChange: (value: string) => void;
  value: string;
}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === 'tr' ? 'tr-TR' : 'en-US';
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const selectedDate = parseScheduleAt(value) ?? defaultScheduleDate();
  const selectedMonth = startOfMonth(selectedDate);
  const [displayMonthOverride, setDisplayMonthOverride] = useState<Date | null>(null);
  const displayMonth = displayMonthOverride ?? selectedMonth;
  const calendarCells = buildCalendarCells(displayMonth);
  const labels = weekdayLabels(locale);

  const updateTime = (nextHours: number, nextMinutes: number) => {
    const next = new Date(selectedDate);
    next.setHours(nextHours, nextMinutes, 0, 0);
    onChange(toScheduleAtValue(next));
  };

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => {
          setDisplayMonthOverride(null);
          setOpen((current) => !current);
        }}
        className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-background/70 px-4 py-3 text-left"
        aria-expanded={open}
        aria-label={t('socialComposePage.editor.schedule')}
      >
        <div className="flex min-w-0 items-center gap-3">
          <CalendarClock className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="truncate text-sm text-foreground">{formatScheduleAt(value, locale)}</span>
        </div>
        <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180 text-primary' : ''}`} />
      </button>

      <FloatingPanel anchorRef={triggerRef} open={open} onClose={() => setOpen(false)} width={340}>
        <div className="space-y-4 p-4">
          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => setDisplayMonthOverride(new Date(displayMonth.getFullYear(), displayMonth.getMonth() - 1, 1))}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-muted-foreground transition hover:border-primary/35 hover:text-primary"
              aria-label={t('socialComposePage.schedulePicker.previousMonth')}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <div className="text-sm font-semibold text-foreground">{monthLabel(displayMonth, locale)}</div>
            <button
              type="button"
              onClick={() => setDisplayMonthOverride(new Date(displayMonth.getFullYear(), displayMonth.getMonth() + 1, 1))}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-muted-foreground transition hover:border-primary/35 hover:text-primary"
              aria-label={t('socialComposePage.schedulePicker.nextMonth')}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="grid grid-cols-7 gap-2 text-center text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
            {labels.map((label) => (
              <div key={label}>{label}</div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-2">
            {calendarCells.map((cell, index) => (
              <button
                key={cell ? cell.toISOString() : `empty-${index}`}
                type="button"
                disabled={!cell}
                onClick={() => {
                  if (!cell) {
                    return;
                  }
                  const next = new Date(selectedDate);
                  next.setFullYear(cell.getFullYear(), cell.getMonth(), cell.getDate());
                  onChange(toScheduleAtValue(next));
                }}
                className={`flex h-10 items-center justify-center rounded-xl border text-sm transition ${
                  !cell
                    ? 'cursor-default border-transparent bg-transparent opacity-0'
                    : isSameDay(cell, selectedDate)
                      ? 'border-primary/40 bg-primary/15 text-primary'
                      : 'border-white/10 bg-white/[0.03] text-foreground hover:border-secondary/35 hover:bg-secondary/10'
                }`}
              >
                {cell?.getDate() ?? ''}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-[1fr_1fr_auto] gap-3">
            <select
              value={`${selectedDate.getHours()}`.padStart(2, '0')}
              onChange={(event) => updateTime(Number(event.target.value), selectedDate.getMinutes())}
              className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3 text-sm text-foreground"
              aria-label={t('socialComposePage.schedulePicker.hours')}
            >
              {Array.from({ length: 24 }, (_, hour) => (
                <option key={hour} value={`${hour}`.padStart(2, '0')}>
                  {`${hour}`.padStart(2, '0')}
                </option>
              ))}
            </select>
            <select
              value={`${selectedDate.getMinutes()}`.padStart(2, '0')}
              onChange={(event) => updateTime(selectedDate.getHours(), Number(event.target.value))}
              className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3 text-sm text-foreground"
              aria-label={t('socialComposePage.schedulePicker.minutes')}
            >
              {Array.from({ length: 60 }, (_, minute) => (
                <option key={minute} value={`${minute}`.padStart(2, '0')}>
                  {`${minute}`.padStart(2, '0')}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => {
                setDisplayMonthOverride(null);
                onChange(toScheduleAtValue(defaultScheduleDate()));
              }}
              className="rounded-xl border border-secondary/35 bg-secondary/12 px-4 py-3 text-xs font-mono uppercase tracking-[0.18em] text-secondary transition hover:border-secondary/55"
            >
              {t('socialComposePage.schedulePicker.today')}
            </button>
          </div>
        </div>
      </FloatingPanel>
    </>
  );
}

export function SocialComposePage() {
  const { t } = useTranslation();
  const [clip, setClip] = useState<Clip | null>(() => readClipFromQuery());
  const [clipOptions, setClipOptions] = useState<Clip[]>([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const controller = useShareComposerController({ clip, open: true });
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
        if (!cancelled) {
          setClipOptions(response.clips ?? []);
        }
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
    if (typeof window !== 'undefined') {
      window.history.replaceState({}, '', buildSocialComposeUrl(selectedClip));
    }
  };

  const handleClearClip = () => {
    setClip(null);
    if (typeof window !== 'undefined') {
      window.history.replaceState({}, '', buildSocialComposeUrl(null));
    }
  };

  return (
    <main className="mx-auto max-w-[1500px] space-y-6">
      <section className="glass-card border-secondary/20 p-6 sm:p-8">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px] xl:items-start">
          <div className="space-y-4 min-w-0">
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
            <div className="flex flex-wrap gap-2 min-w-0">
              <InfoChip label={clip ? resolveProjectId(clip) ?? 'no-project' : 'clip-not-selected'} />
              <InfoChip label={clip?.name ?? t('socialComposePage.clipPicker.choose')} />
              <InfoChip label={getPlatformLabel(controller.selectedPlatform)} />
            </div>
          </div>

          <div className="space-y-3">
            <ClipPicker
              clip={clip}
              clipOptions={clipOptions}
              loading={pickerLoading}
              error={pickerError}
              onClear={handleClearClip}
              onSelect={handleSelectClip}
            />
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
  selectedAccounts,
  selectedPlatform,
}: {
  activeContent: ShareDraftContent | null;
  clip: Clip | null;
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
        <ProtectedPreviewVideo clip={clip} />
      </div>

      {clip && activeContent ? (
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

      <div className="grid gap-3 sm:grid-cols-2">
        <InfoChip label={clip?.name ?? t('socialComposePage.clipPicker.choose')} />
        <InfoChip label={clip ? resolveProjectId(clip) ?? 'no-project' : t('socialComposePage.preview.emptyMeta')} />
      </div>
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
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto_auto_auto] md:items-end">
        <Field label={t('socialComposePage.editor.schedule')}>
          <DateTimePicker value={controller.scheduleAt} onChange={controller.setScheduleAt} />
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
      <div className="flex flex-wrap gap-2">
        <InfoChip label={clip?.name ?? t('socialComposePage.clipPicker.choose')} />
        <InfoChip label={clip ? resolveProjectId(clip) ?? 'no-project' : t('socialComposePage.preview.emptyMeta')} />
        <InfoChip label={getPlatformLabel(controller.selectedPlatform)} />
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
    <div
      className="max-w-full shrink rounded-full border border-border bg-foreground/5 px-3 py-2 text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground sm:max-w-[22rem]"
      title={label}
    >
      <div className="truncate">{label}</div>
    </div>
  );
}
