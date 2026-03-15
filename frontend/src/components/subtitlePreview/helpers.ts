import type { CSSProperties } from 'react';

import {
  ANIMATION_LABELS,
  resolveSubtitleStyle,
  type PreviewAnimationType,
  type PreviewBandVariant,
  type PreviewScreenTheme,
  type SubtitleAnimationType,
  type StyleName,
  type SubtitlePreviewMotion,
} from '../../config/subtitleStyles';

export const PREVIEW_WORDS = ['Bu', 'bir', 'demo', 'altyazi'];

export type PreviewShellType = 'landscape' | 'phone';

export interface SubtitlePreviewModel {
  baseStyleHighlight: CSSProperties;
  baseStylePrimary: CSSProperties;
  bandVariant: PreviewBandVariant;
  hasBackground: boolean;
  highlightColor: string;
  isGlass: boolean;
  shouldUsePlate: boolean;
  motionProfile: SubtitlePreviewMotion;
  motionLabel: string;
  primaryColor: string;
  requestedAnimationType: SubtitleAnimationType;
  resolvedAnimationType: PreviewAnimationType;
  resolvedStyle: StyleName;
  screenTheme: PreviewScreenTheme;
  shellType: PreviewShellType;
  styleLabel: string;
  wrapperStyle: CSSProperties;
}

export function buildTextShadow(outlineColor: string, width: number, isGlow = false): string {
  if (width <= 0 && !isGlow) {
    return 'none';
  }

  if (isGlow) {
    return `0 0 8px ${outlineColor}, 0 0 18px ${outlineColor}, 0 0 28px ${outlineColor}`;
  }

  const spread = `${Math.min(width, 4)}px`;
  return [
    `${spread} ${spread} 0 ${outlineColor}`,
    `-${spread} -${spread} 0 ${outlineColor}`,
    `${spread} -${spread} 0 ${outlineColor}`,
    `-${spread} ${spread} 0 ${outlineColor}`,
    `0 ${spread} 0 ${outlineColor}`,
    `0 -${spread} 0 ${outlineColor}`,
    `${spread} 0 0 ${outlineColor}`,
    `-${spread} 0 0 ${outlineColor}`,
  ].join(', ');
}

export function getSubtitlePreviewModel(
  styleName: string,
  cutAsShort = true,
  animationType: SubtitleAnimationType = 'default',
): SubtitlePreviewModel {
  const resolved = resolveSubtitleStyle(styleName, animationType);
  const style = resolved.inline;
  const shellType: PreviewShellType = cutAsShort ? 'phone' : 'landscape';
  const isGlow = resolved.resolvedStyle === 'GLOW_KARAOKE';
  const isGlass = resolved.resolvedStyle === 'GLASS_MORPH';
  const bandVariant = resolved.preview.bandVariant;
  const shouldUsePlate = bandVariant !== 'plain';
  const outlineWidth = clampOutlineWidth(style.outlineWidth, shellType, isGlow);
  const primaryShadow = buildTextShadow(isGlow ? style.primaryColor : style.outlineColor, outlineWidth, isGlow);
  const highlightShadow = buildTextShadow(isGlow ? style.highlightColor : style.outlineColor, outlineWidth, isGlow);
  const baseStylePrimary: CSSProperties = {
    color: style.primaryColor,
    display: 'inline-block',
    fontFamily: style.fontFamily,
    fontSize: clampPreviewFontSize(style.fontSize, shellType),
    fontStyle: style.fontStyle ?? 'normal',
    fontWeight: style.fontWeight,
    letterSpacing: clampLetterSpacing(style.letterSpacing, shellType),
    lineHeight: shellType === 'phone' ? 1.12 : 1.05,
    textShadow: primaryShadow,
    textTransform: style.textTransform ?? 'none',
    transformOrigin: 'center bottom',
    whiteSpace: 'nowrap',
    ...(style.textDecoration ? { textDecoration: style.textDecoration } : {}),
    ...(isGlass ? { color: 'rgba(255,255,255,0.94)' } : {}),
  };

  return {
    baseStyleHighlight: {
      ...baseStylePrimary,
      color: style.highlightColor,
      textShadow: highlightShadow,
    },
    baseStylePrimary,
    bandVariant,
    hasBackground: style.backgroundColor !== null,
    highlightColor: style.highlightColor,
    isGlass,
    shouldUsePlate,
    motionProfile: resolved.preview.motion,
    motionLabel: resolved.requestedAnimationType === 'default'
      ? `${ANIMATION_LABELS.default} · ${ANIMATION_LABELS[resolved.resolvedAnimationType]}`
      : ANIMATION_LABELS[resolved.resolvedAnimationType],
    primaryColor: style.primaryColor,
    requestedAnimationType: resolved.requestedAnimationType,
    resolvedAnimationType: resolved.resolvedAnimationType,
    resolvedStyle: resolved.resolvedStyle,
    screenTheme: resolved.preview.screenTheme,
    shellType,
    styleLabel: resolved.label,
    wrapperStyle: {
      backgroundColor: style.backgroundColor ?? undefined,
    },
  };
}

export function getPreviewWordStyle(
  index: number,
  activeWordIndex: number,
  preview: SubtitlePreviewModel,
): CSSProperties {
  const isActive = index === activeWordIndex;
  const isPast = index < activeWordIndex;
  const style = isActive ? preview.baseStyleHighlight : preview.baseStylePrimary;
  const visibilityStyle = getVisibilityStyle(index, activeWordIndex, preview.motionProfile.animationType);

  return {
    ...style,
    opacity: resolveOpacity(isActive, isPast, preview.motionProfile.animationType, visibilityStyle.opacity),
    transform: resolveTransform(isActive, preview.motionProfile, preview.shellType),
    transition: `transform ${preview.motionProfile.animationDurationMs}ms cubic-bezier(0.22, 1, 0.36, 1), opacity ${preview.motionProfile.animationDurationMs}ms ease, color ${Math.max(240, preview.motionProfile.animationDurationMs / 2)}ms ease, text-shadow ${Math.max(240, preview.motionProfile.animationDurationMs / 2)}ms ease`,
    ...visibilityStyle,
  };
}

export function getPreviewBandStyle(preview: SubtitlePreviewModel): CSSProperties {
  const duration = Math.max(560, preview.motionProfile.animationDurationMs);

  switch (preview.resolvedAnimationType) {
    case 'pop':
      return {
        animation: `preview-band-pop ${duration}ms cubic-bezier(0.22, 1, 0.36, 1) infinite alternate`,
      };
    case 'shake':
      return {
        animation: 'preview-band-shake 560ms ease-in-out infinite',
      };
    case 'slide_up':
      return {
        animation: `preview-band-slide-up ${Math.max(640, duration)}ms cubic-bezier(0.22, 1, 0.36, 1) infinite alternate`,
      };
    case 'fade':
      return {
        animation: `preview-band-fade ${duration}ms ease-in-out infinite alternate`,
      };
    default:
      return {};
  }
}

function clampPreviewFontSize(fontSize: string, shellType: PreviewShellType): string {
  const parsed = Number.parseFloat(fontSize);
  if (!Number.isFinite(parsed)) {
    return fontSize;
  }

  const scaled = parsed * (shellType === 'phone' ? 0.54 : 0.76);
  const min = shellType === 'phone' ? 0.82 : 1;
  const max = shellType === 'phone' ? 1.22 : 1.9;
  return `${Math.min(max, Math.max(min, scaled)).toFixed(2)}rem`;
}

function clampOutlineWidth(width: number, shellType: PreviewShellType, isGlow: boolean): number {
  if (isGlow) {
    return +(Math.min(width * (shellType === 'phone' ? 0.48 : 0.62), 2.6)).toFixed(2);
  }

  return +(Math.min(width * (shellType === 'phone' ? 0.52 : 0.64), 2.2)).toFixed(2);
}

function clampLetterSpacing(letterSpacing: string | undefined, shellType: PreviewShellType): string | undefined {
  if (!letterSpacing) {
    return undefined;
  }

  const parsed = Number.parseFloat(letterSpacing);
  if (!Number.isFinite(parsed)) {
    return letterSpacing;
  }

  const multiplier = shellType === 'phone' ? 0.64 : 0.84;
  return `${(parsed * multiplier).toFixed(3)}em`;
}

function getVisibilityStyle(
  index: number,
  activeWordIndex: number,
  animationType: PreviewAnimationType,
): CSSProperties {
  if (animationType !== 'typewriter') {
    return {};
  }

  if (index <= activeWordIndex) {
    return {};
  }

  return {
    display: 'none',
    opacity: 0,
    transform: 'translateY(4px) scale(0.98)',
  };
}

function resolveOpacity(
  isActive: boolean,
  isPast: boolean,
  animationType: PreviewAnimationType,
  fallbackOpacity: CSSProperties['opacity'],
): number | CSSProperties['opacity'] {
  if (fallbackOpacity !== undefined) {
    return fallbackOpacity;
  }

  if (isActive) {
    return 1;
  }

  if (animationType === 'fade') {
    return 0.28;
  }

  if (animationType === 'typewriter') {
    return isPast ? 0.9 : 0;
  }

  return 0.78;
}

function resolveTransform(
  isActive: boolean,
  motionProfile: SubtitlePreviewMotion,
  shellType: PreviewShellType,
): string {
  if (!isActive) {
    return 'translate3d(0, 0, 0) scale(1)';
  }

  const emphasisScale = shellType === 'phone'
    ? Math.min(motionProfile.emphasisScale, 1.08)
    : motionProfile.emphasisScale;

  switch (motionProfile.animationType) {
    case 'pop':
      return `translate3d(0, ${shellType === 'phone' ? '-1.5px' : '-1px'}, 0) scale(${Math.min(emphasisScale, shellType === 'phone' ? 1.12 : emphasisScale)})`;
    case 'shake':
      return shellType === 'phone'
        ? `translate3d(-1.25px, -0.75px, 0) rotate(-0.8deg) scale(${Math.min(emphasisScale, 1.08)})`
        : `translate3d(-1px, -1px, 0) rotate(-1deg) scale(${emphasisScale})`;
    case 'slide_up':
      return `translate3d(0, ${shellType === 'phone' ? '-4px' : '-4px'}, 0) scale(${Math.min(emphasisScale, shellType === 'phone' ? 1.05 : emphasisScale)})`;
    default:
      return `translate3d(0, 0, 0) scale(${emphasisScale})`;
  }
}
