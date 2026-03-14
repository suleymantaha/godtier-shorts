import type { CSSProperties } from 'react';

import { SUBTITLE_INLINE_STYLES, isStyleName, type StyleName } from '../../config/subtitleStyles';

export const PREVIEW_WORDS = ['Bu', 'bir', 'ornek', 'altyazi'];
export const HIGHLIGHT_INDEX = 2;

export const STYLE_LABELS: Record<StyleName, string> = {
  HORMOZI: 'Hormozi',
  MRBEAST: 'MrBeast',
  MINIMALIST: 'Minimalist',
  TIKTOK: 'TikTok',
  YOUTUBE_SHORT: 'YouTube Shorts',
  PODCAST: 'Podcast',
  CORPORATE: 'Kurumsal',
  HIGHCARE: 'Yuksek Kontrast',
  CYBER_PUNK: 'Cyber Glitch',
  STORY_TELLER: 'Storyteller',
  GLOW_KARAOKE: 'Neon Karaoke',
  GLASS_MORPH: 'Glassmorphism',
  ALI_ABDAAL: 'Productivity Vlog',
  RETRO_WAVE: '80s Synthwave',
  HACKER_TERMINAL: 'Terminal Code',
  CINEMATIC_FILM: 'Documentary Film',
  CUSTOM: 'Ozel',
};

export interface SubtitlePreviewModel {
  baseStyleHighlight: CSSProperties;
  baseStylePrimary: CSSProperties;
  hasBackground: boolean;
  highlightColor: string;
  isGlass: boolean;
  isTypewriter: boolean;
  primaryColor: string;
  resolvedStyle: StyleName;
  styleLabel: string;
  wrapperStyle: CSSProperties;
}

export function buildTextShadow(outlineColor: string, width: number, isGlow = false): string {
  if (width <= 0 && !isGlow) {
    return 'none';
  }

  if (isGlow) {
    return `0 0 10px ${outlineColor}, 0 0 20px ${outlineColor}, 0 0 30px ${outlineColor}`;
  }

  const spread = `${Math.min(width, 6)}px`;
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

export function getSubtitlePreviewModel(styleName: string): SubtitlePreviewModel {
  const resolvedStyle: StyleName = isStyleName(styleName) ? styleName : 'HORMOZI';
  const style = SUBTITLE_INLINE_STYLES[resolvedStyle];
  const isGlow = resolvedStyle === 'GLOW_KARAOKE';
  const isGlass = resolvedStyle === 'GLASS_MORPH';
  const primaryShadow = buildTextShadow(isGlow ? style.primaryColor : style.outlineColor, style.outlineWidth, isGlow);
  const highlightShadow = buildTextShadow(isGlow ? style.highlightColor : style.outlineColor, style.outlineWidth, isGlow);
  const baseStylePrimary: CSSProperties = {
    color: style.primaryColor,
    fontFamily: style.fontFamily,
    fontSize: style.fontSize,
    fontWeight: style.fontWeight,
    lineHeight: 1.3,
    textShadow: primaryShadow,
    ...(isGlass ? { color: 'rgba(255,255,255,0.9)' } : {}),
  };

  return {
    baseStyleHighlight: {
      ...baseStylePrimary,
      color: style.highlightColor,
      textShadow: highlightShadow,
    },
    baseStylePrimary,
    hasBackground: style.backgroundColor !== null,
    highlightColor: style.highlightColor,
    isGlass,
    isTypewriter: resolvedStyle === 'STORY_TELLER',
    primaryColor: style.primaryColor,
    resolvedStyle,
    styleLabel: STYLE_LABELS[resolvedStyle],
    wrapperStyle: {
      backgroundColor: style.backgroundColor ?? undefined,
    },
  };
}
