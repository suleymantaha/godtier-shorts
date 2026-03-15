import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { EyeOff, MonitorPlay, Smartphone, Subtitles } from 'lucide-react';

import {
  type PreviewScreenTheme,
  type SubtitleAnimationType,
  type SubtitleLayout,
  getSubtitleBoxStyle,
} from '../config/subtitleStyles';
import { useResolvedMediaSource } from './ui/protectedMedia';
import { PREVIEW_WORDS, getPreviewBandStyle, getPreviewWordStyle, getSubtitlePreviewModel } from './subtitlePreview/helpers';

interface SubtitlePreviewProps {
  animationType?: SubtitleAnimationType;
  cutAsShort?: boolean;
  disabled: boolean;
  layout?: SubtitleLayout;
  showLegend?: boolean;
  size?: 'compact' | 'default' | 'tall';
  styleName: string;
  videoSrc?: string;
  variant?: 'card' | 'device';
}

export function SubtitlePreview({
  animationType = 'default',
  styleName,
  disabled,
  cutAsShort = true,
  layout = 'single',
  showLegend = true,
  size = 'default',
  videoSrc,
  variant = 'card',
}: SubtitlePreviewProps) {
  const preview = getSubtitlePreviewModel(styleName, cutAsShort, animationType);
  const resolvedVideoSrc = useResolvedMediaSource(videoSrc);
  const [activeWordIndex, setActiveWordIndex] = useState(0);

  useEffect(() => {
    const resetId = window.setTimeout(() => {
      setActiveWordIndex(0);
    }, 0);

    if (disabled) {
      return () => window.clearTimeout(resetId);
    }

    const intervalId = window.setInterval(() => {
      setActiveWordIndex((current) => (current + 1) % PREVIEW_WORDS.length);
    }, preview.motionProfile.animationDurationMs);

    return () => {
      window.clearTimeout(resetId);
      window.clearInterval(intervalId);
    };
  }, [disabled, preview.motionProfile.animationDurationMs, preview.resolvedStyle]);

  const previewBody = (
    <PreviewSurface size={size} variant={variant}>
      <EnabledPreview
        activeWordIndex={activeWordIndex}
        disabled={disabled}
        layout={layout}
        preview={preview}
        resolvedVideoSrc={resolvedVideoSrc}
        size={size}
        variant={variant}
      />
    </PreviewSurface>
  );

  if (variant === 'device') {
    const isCondensedDevice = size !== 'default';

    return (
      <div className={`flex w-full flex-col items-center justify-center ${isCondensedDevice ? 'h-full gap-3' : 'gap-4'}`}>
        {previewBody}
        {size === 'default' ? (
          <div className="flex flex-wrap items-center justify-center gap-2 text-[11px] font-mono text-muted-foreground/65">
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
              {cutAsShort ? 'Short' : 'Landscape'}
            </span>
            <span className={disabled ? 'opacity-45' : ''}>{preview.styleLabel}</span>
            <span className={disabled ? 'opacity-45' : ''}>{preview.motionLabel}</span>
          </div>
        ) : null}
        {!disabled && showLegend && size === 'default' ? <ColorLegend highlightColor={preview.highlightColor} primaryColor={preview.primaryColor} /> : null}
      </div>
    );
  }

  return (
    <section className="glass-card p-6 border-accent/10 ring-1 ring-accent/5">
      <PreviewHeader
        cutAsShort={cutAsShort}
        disabled={disabled}
        motionLabel={preview.motionLabel}
        styleLabel={preview.styleLabel}
      />
      {previewBody}
      {!disabled && showLegend ? <ColorLegend highlightColor={preview.highlightColor} primaryColor={preview.primaryColor} /> : null}
    </section>
  );
}

function PreviewHeader({
  cutAsShort,
  disabled,
  motionLabel,
  styleLabel,
}: {
  cutAsShort: boolean;
  disabled: boolean;
  motionLabel: string;
  styleLabel: string;
}) {
  const ShellIcon = cutAsShort ? Smartphone : MonitorPlay;
  const shellLabel = cutAsShort ? 'Short' : 'Landscape';

  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <Subtitles className="h-4 w-4 text-accent/70" aria-hidden="true" />
        <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-accent/80">
          Altyazi Onizleme
        </h3>
      </div>
      <div className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground/60">
        <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-1">
          <ShellIcon className="h-3 w-3" aria-hidden="true" />
          {shellLabel}
        </span>
        <span className={disabled ? 'opacity-45' : ''}>{styleLabel}</span>
        <span className={disabled ? 'opacity-45' : ''}>{motionLabel}</span>
      </div>
    </div>
  );
}

function EnabledPreview({
  activeWordIndex,
  disabled,
  layout,
  preview,
  resolvedVideoSrc,
  size,
  variant,
}: {
  activeWordIndex: number;
  disabled: boolean;
  layout: SubtitleLayout;
  preview: ReturnType<typeof getSubtitlePreviewModel>;
  resolvedVideoSrc?: string;
  size: 'compact' | 'default' | 'tall';
  variant: 'card' | 'device';
}) {
  const boxStyle: CSSProperties = {
    ...getSubtitleBoxStyle(layout, 'preview'),
    position: 'absolute',
  };
  const shellClassName = preview.shellType === 'phone'
    ? `relative aspect-[9/19] max-w-full rounded-[34px] border border-white/[0.12] bg-[#121218] p-[10px] shadow-[0_28px_100px_rgba(0,0,0,0.55)] ${resolvePhoneShellHeightClassName(variant, size)}`
    : `relative aspect-video w-full max-w-[520px] rounded-[28px] border border-white/[0.12] bg-[#121218] p-[8px] shadow-[0_28px_100px_rgba(0,0,0,0.5)] ${variant === 'device' ? 'min-h-[260px]' : ''}`;
  const screenClassName = preview.shellType === 'phone'
    ? 'relative h-full w-full overflow-hidden rounded-[26px] border border-white/10'
    : 'relative h-full w-full overflow-hidden rounded-[22px] border border-white/10';

  return (
    <div className="relative flex h-full w-full items-center justify-center">
      <div
        aria-label="subtitle-preview-stage"
        className={shellClassName}
        data-preview-size={size}
        data-shell-type={preview.shellType}
      >
        {preview.shellType === 'phone' && (
          <div className="pointer-events-none absolute left-1/2 top-[16px] z-20 h-[18px] w-[96px] -translate-x-1/2 rounded-full bg-black/70 shadow-[0_2px_12px_rgba(0,0,0,0.4)]" />
        )}
        <div className={screenClassName}>
          <PreviewBackdrop
            hasVideo={Boolean(resolvedVideoSrc)}
            layout={layout}
            preview={preview}
          />
          {resolvedVideoSrc ? (
            <video
              aria-hidden="true"
              autoPlay
              className="absolute inset-0 h-full w-full object-cover opacity-50 saturate-150"
              data-testid="subtitle-preview-media"
              loop
              muted
              playsInline
              src={resolvedVideoSrc}
            />
          ) : null}
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.08),_transparent_42%)]" />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,_transparent_0%,_transparent_46%,_rgba(0,0,0,0.22)_100%)]" />
          {!disabled ? (
            <div className="absolute inset-0">
              <div className="absolute flex items-end justify-center" style={boxStyle}>
                <PreviewSubtitleBand activeWordIndex={activeWordIndex} preview={preview} />
              </div>
            </div>
          ) : null}
          {disabled ? <DisabledOverlay /> : null}
        </div>
      </div>
    </div>
  );
}

function PreviewSurface({
  children,
  size,
  variant,
}: {
  children: ReactNode;
  size: 'compact' | 'default' | 'tall';
  variant: 'card' | 'device';
}) {
  if (variant === 'device') {
    const surfaceClassName = size === 'compact'
      ? 'min-h-[320px] sm:min-h-[360px] lg:h-full lg:min-h-0'
      : size === 'tall'
        ? 'min-h-[420px] sm:min-h-[500px] lg:h-full lg:min-h-0'
        : 'min-h-[420px] sm:min-h-[480px] lg:min-h-[540px]';

    return (
      <div className={`relative flex w-full items-center justify-center ${surfaceClassName}`}>
        {children}
      </div>
    );
  }

  return (
    <div className="relative flex min-h-[320px] items-center justify-center overflow-hidden rounded-[28px] border border-white/[0.06] bg-[radial-gradient(circle_at_top,_rgba(255,0,128,0.12),_transparent_42%),linear-gradient(180deg,_rgba(8,8,14,0.98),_rgba(2,2,6,0.94))] px-4 py-6">
      <div className="absolute inset-0 bg-[linear-gradient(120deg,_rgba(255,255,255,0.04),_transparent_30%,_transparent_70%,_rgba(255,255,255,0.03))]" />
      {children}
    </div>
  );
}

function resolvePhoneShellHeightClassName(variant: 'card' | 'device', size: 'compact' | 'default' | 'tall') {
  if (variant !== 'device') {
    return 'h-[320px]';
  }

  if (size === 'compact') {
    return 'h-[clamp(320px,34vw,420px)] lg:h-full lg:max-h-[680px]';
  }

  if (size === 'tall') {
    return 'h-[clamp(360px,66vw,520px)] lg:h-full lg:max-h-none';
  }

  return 'h-[clamp(380px,46vw,500px)]';
}

function PreviewBackdrop({
  hasVideo,
  layout,
  preview,
}: {
  hasVideo: boolean;
  layout: SubtitleLayout;
  preview: ReturnType<typeof getSubtitlePreviewModel>;
}) {
  return (
    <>
      <div className={`absolute inset-0 ${getScreenThemeClassName(preview.screenTheme, hasVideo)}`} />
      {layout === 'split' ? (
        <>
          <div className="absolute inset-x-0 top-0 h-[44%] border-b border-white/[0.08] bg-black/[0.12]" />
          <div className="absolute inset-x-0 bottom-0 h-[44%] border-t border-white/[0.08] bg-black/20" />
        </>
      ) : null}
      <div className="absolute inset-0 bg-[linear-gradient(135deg,_rgba(255,255,255,0.07),_transparent_22%,_transparent_75%,_rgba(255,255,255,0.03))]" />
    </>
  );
}

function PreviewSubtitleBand({
  activeWordIndex,
  preview,
}: {
  activeWordIndex: number;
  preview: ReturnType<typeof getSubtitlePreviewModel>;
}) {
  const mode = preview.bandVariant;
  const containerClassName = 'relative w-full max-w-full text-center';
  const contentClassName = getBandContentClassName(preview);
  const contentStyle: CSSProperties = {
    textWrap: 'balance',
    ...getBandContentStyle(preview),
  };
  const bandMotionStyle = getPreviewBandStyle(preview);

  return (
    <div
      className={containerClassName}
      data-preview-band-mode={mode}
      data-preview-motion={preview.resolvedAnimationType}
      data-testid="subtitle-preview-band"
      style={bandMotionStyle}
    >
      <div className={contentClassName} style={contentStyle}>
        {PREVIEW_WORDS.map((word, index) => (
          <span
            key={word}
            data-active={index === activeWordIndex ? 'true' : 'false'}
            data-testid={`subtitle-preview-word-${index}`}
            style={getPreviewWordStyle(index, activeWordIndex, preview)}
          >
            {word}
          </span>
        ))}
      </div>
    </div>
  );
}

function getBandContentClassName(preview: ReturnType<typeof getSubtitlePreviewModel>) {
  const spacing = preview.shellType === 'phone'
    ? 'gap-x-1 gap-y-0.5 px-2.5 py-1.5'
    : 'gap-x-2 gap-y-1.5 px-4 py-3';

  switch (preview.bandVariant) {
    case 'bold_plate':
      return `mx-auto inline-flex max-w-full flex-wrap items-center justify-center overflow-hidden rounded-[15px] border border-white/10 shadow-[0_14px_30px_rgba(0,0,0,0.28)] ${spacing}`;
    case 'soft_plate':
      return `mx-auto inline-flex max-w-full flex-wrap items-center justify-center overflow-hidden rounded-[16px] border border-white/8 shadow-[0_10px_24px_rgba(0,0,0,0.18)] ${spacing}`;
    case 'glass_plate':
      return `mx-auto inline-flex max-w-full flex-wrap items-center justify-center overflow-hidden rounded-[18px] border border-white/18 shadow-[0_16px_34px_rgba(0,0,0,0.22)] backdrop-blur-md ${spacing}`;
    case 'terminal_plate':
      return `mx-auto inline-flex max-w-full flex-wrap items-center justify-center overflow-hidden rounded-[10px] border border-emerald-400/20 shadow-[0_12px_30px_rgba(0,0,0,0.24)] ${spacing}`;
    default:
      return `mx-auto flex w-full max-w-full flex-wrap items-center justify-center overflow-hidden ${preview.shellType === 'phone' ? 'gap-x-1 gap-y-0.5 px-0 py-0.5' : 'gap-x-2 gap-y-1.5'}`;
  }
}

function getBandContentStyle(preview: ReturnType<typeof getSubtitlePreviewModel>): CSSProperties {
  switch (preview.bandVariant) {
    case 'bold_plate':
      return {
        backgroundColor: preview.wrapperStyle.backgroundColor ?? 'rgba(0, 0, 0, 0.62)',
      };
    case 'soft_plate':
      return {
        backgroundColor: preview.wrapperStyle.backgroundColor ?? 'rgba(0, 0, 0, 0.36)',
        backdropFilter: 'blur(3px)',
      };
    case 'glass_plate':
      return {
        backgroundColor: preview.wrapperStyle.backgroundColor ?? 'rgba(255, 255, 255, 0.12)',
        backdropFilter: 'blur(10px)',
      };
    case 'terminal_plate':
      return {
        backgroundColor: preview.wrapperStyle.backgroundColor ?? 'rgba(0, 0, 0, 0.7)',
        boxShadow: 'inset 0 0 0 1px rgba(16, 185, 129, 0.14), 0 0 18px rgba(16, 185, 129, 0.08)',
      };
    default:
      return {};
  }
}

function DisabledOverlay() {
  return (
    <div
      className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-black/55 text-sm font-mono text-muted-foreground/80 backdrop-blur-[2px]"
      data-testid="subtitle-preview-disabled"
    >
      <EyeOff className="h-5 w-5" aria-hidden="true" />
      <span>Altyazi devre disi</span>
    </div>
  );
}

function ColorLegend({
  highlightColor,
  primaryColor,
}: {
  highlightColor: string;
  primaryColor: string;
}) {
  return (
    <div className="mt-3 flex items-center justify-center gap-3">
      <ColorLegendItem color={primaryColor} label="primary" />
      {primaryColor !== highlightColor ? <ColorLegendItem color={highlightColor} label="highlight" /> : null}
    </div>
  );
}

function ColorLegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-full border border-white/20" style={{ backgroundColor: color }} />
      <span className="text-[10px] font-mono text-muted-foreground/40">{label}</span>
    </div>
  );
}

function getScreenThemeClassName(screenTheme: PreviewScreenTheme, hasVideo: boolean): string {
  if (hasVideo) {
    return 'bg-[linear-gradient(180deg,_rgba(4,4,6,0.08),_rgba(4,4,6,0.36))]';
  }

  switch (screenTheme) {
    case 'glass':
      return 'bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.26),_transparent_40%),linear-gradient(180deg,_rgba(58,84,122,0.7),_rgba(17,18,24,0.95))]';
    case 'minimal':
      return 'bg-[linear-gradient(180deg,_rgba(34,34,40,0.82),_rgba(12,12,16,0.96))]';
    case 'neon':
      return 'bg-[radial-gradient(circle_at_top_left,_rgba(255,0,128,0.28),_transparent_34%),radial-gradient(circle_at_top_right,_rgba(0,255,255,0.22),_transparent_30%),linear-gradient(180deg,_rgba(15,10,25,0.94),_rgba(6,6,12,0.98))]';
    case 'terminal':
      return 'bg-[radial-gradient(circle_at_top,_rgba(0,255,153,0.18),_transparent_42%),linear-gradient(180deg,_rgba(2,12,8,0.96),_rgba(0,0,0,0.98))]';
    case 'cinematic':
      return 'bg-[radial-gradient(circle_at_top,_rgba(255,220,166,0.18),_transparent_40%),linear-gradient(180deg,_rgba(27,30,38,0.92),_rgba(7,7,9,0.98))]';
    default:
      return 'bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.12),_transparent_42%),linear-gradient(180deg,_rgba(42,44,58,0.88),_rgba(9,10,16,0.96))]';
  }
}
