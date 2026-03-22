import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type MouseEvent,
  type TouchEvent,
} from 'react';
import { useTranslation } from 'react-i18next';

import type { Segment } from '../types';
import {
  getSubtitleBoxStyle,
  resolveSubtitleStyle,
  type StyleName,
  type SubtitleAnimationType,
  type SubtitleLayout,
  type SubtitleSafeAreaProfile,
} from '../config/subtitleStyles';
import { buildTextShadow } from './subtitlePreview/helpers';
import { getSubtitleChunkLines } from '../utils/subtitleTiming';
import {
  buildCropGuideStyle,
  findCurrentSubtitleState,
  getCropFromClientX,
  getNextCropValue,
} from './videoOverlay/helpers';

interface VideoOverlayProps {
  animationType?: SubtitleAnimationType;
  currentTime: number;
  transcript: Segment[];
  style: StyleName;
  centerX: number;
  onCropChange: (x: number) => void;
  layout?: SubtitleLayout;
  safeAreaProfile?: SubtitleSafeAreaProfile;
}

export function VideoOverlay({
  animationType = 'default',
  currentTime,
  transcript,
  style,
  centerX,
  onCropChange,
  layout = 'single',
  safeAreaProfile = 'default',
}: VideoOverlayProps) {
  const resolvedStyle = useMemo(
    () => resolveSubtitleStyle(style, animationType),
    [animationType, style],
  );
  const fontSizeRem = useMemo(
    () => Number.parseFloat(resolvedStyle.inline.fontSize) || 2.4,
    [resolvedStyle.inline.fontSize],
  );
  const currentSubtitleState = useMemo(
    () => findCurrentSubtitleState(transcript, currentTime, {
      layout,
      fontSizeRem,
      fontWeight: resolvedStyle.inline.fontWeight,
    }),
    [currentTime, fontSizeRem, layout, resolvedStyle.inline.fontWeight, transcript],
  );

  const handleMouseDown = useCallback((e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();

    const onMouseMove = (moveEvent: globalThis.MouseEvent) => {
      onCropChange(getCropFromClientX(moveEvent.clientX, rect));
    };
    const onMouseUp = () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);

    onCropChange(getCropFromClientX(e.clientX, rect));
  }, [onCropChange]);

  const handleTouchStart = useCallback((e: TouchEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const touch = e.touches[0];
    if (touch) {
      onCropChange(getCropFromClientX(touch.clientX, rect));
    }

    const onTouchMove = (moveEvent: globalThis.TouchEvent) => {
      const nextTouch = moveEvent.touches[0];
      if (nextTouch) {
        onCropChange(getCropFromClientX(nextTouch.clientX, rect));
      }
    };
    const onTouchEnd = () => {
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onTouchEnd);
    };

    window.addEventListener('touchmove', onTouchMove, { passive: true });
    window.addEventListener('touchend', onTouchEnd);
  }, [onCropChange]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    const next = getNextCropValue(centerX, e.key);
    if (next === null) {
      return;
    }
    e.preventDefault();
    onCropChange(next);
  }, [centerX, onCropChange]);

  return (
    <div
      className="absolute inset-0 cursor-crosshair select-none"
      onMouseDown={handleMouseDown}
      onTouchStart={handleTouchStart}
    >
      <CropGuide centerX={centerX} />
      <LiveSubtitle currentSubtitleState={currentSubtitleState} resolved={resolvedStyle} layout={layout} safeAreaProfile={safeAreaProfile} />
      <CropSlider centerX={centerX} onKeyDown={handleKeyDown} />
    </div>
  );
}

function CropGuide({ centerX }: { centerX: number }) {
  return (
    <div
      className="absolute top-0 bottom-0 pointer-events-none border-2 border-dashed border-foreground/30 bg-foreground/5 transition-all duration-75"
      style={buildCropGuideStyle(centerX)}
    >
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="h-1 w-1 rounded-full bg-foreground opacity-50" />
      </div>
    </div>
  );
}

function LiveSubtitle({
  currentSubtitleState,
  resolved,
  layout,
  safeAreaProfile,
}: {
  currentSubtitleState: ReturnType<typeof findCurrentSubtitleState>;
  resolved: ReturnType<typeof resolveSubtitleStyle>;
  layout: SubtitleLayout;
  safeAreaProfile: SubtitleSafeAreaProfile;
}) {
  const [entered, setEntered] = useState(resolved.resolvedAnimationType === 'none');

  useEffect(() => {
    const resetId = window.setTimeout(() => {
      setEntered(resolved.resolvedAnimationType === 'none');
    }, 0);

    if (!currentSubtitleState || resolved.resolvedAnimationType === 'none') {
      return () => window.clearTimeout(resetId);
    }

    const frame = window.setTimeout(() => setEntered(true), 24);
    return () => {
      window.clearTimeout(resetId);
      window.clearTimeout(frame);
    };
  }, [currentSubtitleState, resolved.resolvedAnimationType]);

  if (!currentSubtitleState) {
    return null;
  }

  const inline = resolved.inline;
  const outlineSource = resolved.resolvedStyle === 'GLOW_KARAOKE' ? inline.primaryColor : inline.outlineColor;
  const motionProfile = resolved.preview.motion;
  const textStyle: CSSProperties = {
    color: inline.primaryColor,
    fontFamily: inline.fontFamily,
    fontSize: scaleCssFontSize(inline.fontSize, currentSubtitleState.chunk.fontScale),
    fontStyle: inline.fontStyle ?? 'normal',
    fontWeight: inline.fontWeight,
    letterSpacing: inline.letterSpacing,
    lineHeight: 1.15,
    textAlign: 'center',
    textShadow: buildTextShadow(outlineSource, inline.outlineWidth, resolved.resolvedStyle === 'GLOW_KARAOKE'),
    textTransform: inline.textTransform ?? 'none',
    opacity: entered ? 1 : resolveOverlayBaseOpacity(resolved.resolvedAnimationType),
    transform: entered
      ? 'translate3d(0, 0, 0) scale(1)'
      : resolveOverlayBaseTransform(resolved.resolvedAnimationType),
    transition: `transform ${motionProfile.animationDurationMs}ms cubic-bezier(0.22, 1, 0.36, 1), opacity ${motionProfile.animationDurationMs}ms ease`,
  };
  const wrapperStyle: CSSProperties = {
    ...getSubtitleBoxStyle(layout, 'overlay', safeAreaProfile),
    backgroundColor: inline.backgroundColor ?? undefined,
  };
  const chunkLines = getSubtitleChunkLines(currentSubtitleState.chunk);
  const activeWordIndex = currentSubtitleState.activeWordIndex;

  return (
    <div className="pointer-events-none absolute flex items-center justify-center" style={wrapperStyle}>
      <div
        className={`max-w-full break-words text-center drop-shadow-[0_4px_4px_rgba(0,0,0,1)] ${resolved.overlayClassName}`}
        style={textStyle}
      >
        {chunkLines.map((line, lineIndex) => (
          <SubtitleLine
            activeWordIndex={activeWordIndex ?? -1}
            highlightColor={inline.highlightColor}
            key={`line-${lineIndex}`}
            line={line}
            lineIndex={lineIndex}
            lines={chunkLines}
          />
        ))}
      </div>
    </div>
  );
}

function SubtitleLine({
  activeWordIndex,
  highlightColor,
  line,
  lineIndex,
  lines,
}: {
  activeWordIndex: number;
  highlightColor: string;
  line: ReturnType<typeof getSubtitleChunkLines>[number];
  lineIndex: number;
  lines: ReturnType<typeof getSubtitleChunkLines>;
}) {
  return (
    <div data-testid={`live-subtitle-line-${lineIndex}`}>
      {line.map((word, index) => {
        const globalIndex = getLineWordOffset(lines, lineIndex) + index;
        return (
          <span
            key={`${word.start}-${word.word}`}
            style={globalIndex === activeWordIndex ? { color: highlightColor } : undefined}
          >
            {index > 0 ? ' ' : null}
            {word.word}
          </span>
        );
      })}
    </div>
  );
}

function getLineWordOffset(lines: ReturnType<typeof getSubtitleChunkLines>, lineIndex: number): number {
  return lines
    .slice(0, lineIndex)
    .reduce((sum, candidate) => sum + candidate.length, 0);
}

function scaleCssFontSize(fontSize: string | number | undefined, fontScale?: number): string | number | undefined {
  if (!fontSize || !fontScale || fontScale >= 0.9999) {
    return fontSize;
  }
  if (typeof fontSize === 'number') {
    return +(fontSize * fontScale).toFixed(2);
  }
  const parsed = Number.parseFloat(fontSize);
  if (!Number.isFinite(parsed)) {
    return fontSize;
  }
  const unit = fontSize.replace(String(parsed), '') || 'px';
  return `${(parsed * fontScale).toFixed(3)}${unit}`;
}

function resolveOverlayBaseOpacity(animationType: ReturnType<typeof resolveSubtitleStyle>['resolvedAnimationType']): number {
  switch (animationType) {
    case 'fade':
    case 'slide_up':
      return 0;
    case 'shake':
      return 0.45;
    case 'typewriter':
      return 0.2;
    default:
      return 0.78;
  }
}

function resolveOverlayBaseTransform(animationType: ReturnType<typeof resolveSubtitleStyle>['resolvedAnimationType']): string {
  switch (animationType) {
    case 'pop':
      return 'translate3d(0, 4px, 0) scale(0.94)';
    case 'shake':
      return 'translate3d(-3px, 1px, 0) rotate(-1deg) scale(0.98)';
    case 'slide_up':
      return 'translate3d(0, 12px, 0) scale(1)';
    case 'typewriter':
      return 'translate3d(0, 0, 0) scale(1)';
    default:
      return 'translate3d(0, 0, 0) scale(1)';
  }
}

function CropSlider({
  centerX,
  onKeyDown,
}: {
  centerX: number;
  onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void;
}) {
  const { t } = useTranslation();

  return (
    <div
      role="slider"
      tabIndex={0}
      aria-label={t('media.cropPosition')}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(centerX * 100)}
      onKeyDown={onKeyDown}
      className="absolute left-3 top-3 rounded border border-border bg-background/80 px-3 py-1.5 text-[11px] font-mono text-foreground/70 backdrop-blur-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
    >
      {t('media.cropValue', { value: (centerX * 100).toFixed(1) })}
    </div>
  );
}
