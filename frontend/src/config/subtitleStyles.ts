import type { CSSProperties } from 'react';

export type SubtitleLayout = 'single' | 'split';
export type SubtitleSurface = 'overlay' | 'preview';
export type PreviewAnimationType = 'fade' | 'none' | 'pop' | 'shake' | 'slide_up' | 'typewriter';
export type SubtitleAnimationType = 'default' | PreviewAnimationType;
export type PreviewScreenTheme = 'cinematic' | 'glass' | 'minimal' | 'neon' | 'studio' | 'terminal';
export type PreviewBandVariant = 'plain' | 'bold_plate' | 'soft_plate' | 'glass_plate' | 'terminal_plate';

export interface SubtitleInlineStyle {
  primaryColor: string;
  highlightColor: string;
  outlineColor: string;
  outlineWidth: number;
  fontSize: string;
  fontWeight: number;
  fontFamily: string;
  backgroundColor: string | null;
  fontStyle?: 'normal' | 'italic';
  letterSpacing?: string;
  textDecoration?: string;
  textTransform?: 'none' | 'uppercase';
}

export interface SubtitlePreviewMotion {
  animationDurationMs: number;
  animationType: PreviewAnimationType;
  emphasisScale: number;
}

interface SubtitlePreviewDefinition {
  bandVariant: PreviewBandVariant;
  motion: SubtitlePreviewMotion;
  screenTheme: PreviewScreenTheme;
}

interface SubtitleStyleDefinition {
  label: string;
  overlayClassName: string;
  inline: SubtitleInlineStyle;
  preview: SubtitlePreviewDefinition;
}

interface SubtitleAnimationDefinition {
  label: string;
  motion: SubtitlePreviewMotion;
}

function assToHex(ass: string): string {
  const h = ass.replace('&H', '');
  const r = h.slice(6, 8);
  const g = h.slice(4, 6);
  const b = h.slice(2, 4);
  return `#${r}${g}${b}`;
}

function assToRgba(ass: string): string {
  const h = ass.replace('&H', '');
  const a = parseInt(h.slice(0, 2), 16);
  const r = parseInt(h.slice(6, 8), 16);
  const g = parseInt(h.slice(4, 6), 16);
  const b = parseInt(h.slice(2, 4), 16);
  const alpha = +(1 - a / 255).toFixed(2);
  return `rgba(${r},${g},${b},${alpha})`;
}

function scaleRem(rem: string, factor = 1.08): string {
  const numeric = Number.parseFloat(rem);
  return `${(numeric * factor).toFixed(2)}rem`;
}

function softenOutline(width: number, factor = 0.78): number {
  return +(width * factor).toFixed(2);
}

function preview(
  animationType: PreviewAnimationType,
  animationDurationMs: number,
  emphasisScale: number,
  screenTheme: PreviewScreenTheme,
  bandVariant: PreviewBandVariant = 'plain',
): SubtitlePreviewDefinition {
  return {
    bandVariant,
    motion: {
      animationDurationMs,
      animationType,
      emphasisScale,
    },
    screenTheme,
  };
}

export const STYLE_REGISTRY = {
  HORMOZI: {
    label: 'Hormozi',
    overlayClassName: 'font-black uppercase tracking-tight',
    preview: preview('pop', 820, 1.16, 'studio'),
    inline: {
      primaryColor: assToHex('&H00FFFFFF'),
      highlightColor: assToHex('&H0000FFFF'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: softenOutline(8),
      fontSize: scaleRem('2.4rem'),
      fontWeight: 900,
      fontFamily: '"Montserrat", "Outfit", sans-serif',
      backgroundColor: null,
      letterSpacing: '-0.02em',
      textTransform: 'uppercase',
    },
  },
  MRBEAST: {
    label: 'MrBeast',
    overlayClassName: 'font-black uppercase tracking-tight',
    preview: preview('pop', 760, 1.18, 'neon'),
    inline: {
      primaryColor: assToHex('&H00FFFFFF'),
      highlightColor: assToHex('&H0000FF00'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: softenOutline(9),
      fontSize: scaleRem('2.15rem'),
      fontWeight: 900,
      fontFamily: '"Komika Axis", "Outfit", sans-serif',
      backgroundColor: null,
      letterSpacing: '-0.02em',
      textTransform: 'uppercase',
    },
  },
  MINIMALIST: {
    label: 'Minimalist',
    overlayClassName: 'font-medium',
    preview: preview('fade', 980, 1.04, 'minimal'),
    inline: {
      primaryColor: assToHex('&H00E0E0E0'),
      highlightColor: assToHex('&H00FFFFFF'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: 0,
      fontSize: scaleRem('1rem'),
      fontWeight: 400,
      fontFamily: '"Helvetica Neue", "Inter", sans-serif',
      backgroundColor: null,
      textTransform: 'none',
    },
  },
  TIKTOK: {
    label: 'TikTok',
    overlayClassName: 'font-black uppercase tracking-tight',
    preview: preview('slide_up', 720, 1.14, 'neon'),
    inline: {
      primaryColor: assToHex('&H00FFFFFF'),
      highlightColor: assToHex('&H00FF00FF'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: softenOutline(7),
      fontSize: scaleRem('2.2rem'),
      fontWeight: 900,
      fontFamily: '"Montserrat", "Outfit", sans-serif',
      backgroundColor: null,
      letterSpacing: '-0.02em',
      textTransform: 'uppercase',
    },
  },
  YOUTUBE_SHORT: {
    label: 'YouTube Shorts',
    overlayClassName: 'font-bold uppercase tracking-tight',
    preview: preview('pop', 820, 1.1, 'studio', 'bold_plate'),
    inline: {
      primaryColor: assToHex('&H00FFFFFF'),
      highlightColor: assToHex('&H0000FFFF'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: softenOutline(8),
      fontSize: scaleRem('1.85rem'),
      fontWeight: 700,
      fontFamily: '"Poppins", "Outfit", sans-serif',
      backgroundColor: assToRgba('&H80000000'),
      textTransform: 'uppercase',
    },
  },
  PODCAST: {
    label: 'Podcast',
    overlayClassName: 'font-medium',
    preview: preview('fade', 1050, 1.02, 'cinematic', 'soft_plate'),
    inline: {
      primaryColor: assToHex('&H00F0F0F0'),
      highlightColor: assToHex('&H00FFFFFF'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: 0,
      fontSize: scaleRem('1.1rem'),
      fontWeight: 500,
      fontFamily: '"Inter", sans-serif',
      backgroundColor: assToRgba('&H40000000'),
      textTransform: 'none',
    },
  },
  CORPORATE: {
    label: 'Kurumsal',
    overlayClassName: 'font-medium',
    preview: preview('none', 1000, 1.01, 'studio'),
    inline: {
      primaryColor: assToHex('&H00FFFFFF'),
      highlightColor: assToHex('&H00FFFFFF'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: softenOutline(2),
      fontSize: scaleRem('1.15rem'),
      fontWeight: 500,
      fontFamily: '"Roboto", "Inter", sans-serif',
      backgroundColor: null,
      textTransform: 'none',
    },
  },
  HIGHCARE: {
    label: 'Yüksek Kontrast',
    overlayClassName: 'font-black uppercase',
    preview: preview('shake', 700, 1.12, 'studio'),
    inline: {
      primaryColor: assToHex('&H00FFFF00'),
      highlightColor: assToHex('&H00FFFFFF'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: softenOutline(4),
      fontSize: scaleRem('1.45rem'),
      fontWeight: 900,
      fontFamily: '"Arial Black", "Outfit", sans-serif',
      backgroundColor: null,
      textTransform: 'uppercase',
    },
  },
  CYBER_PUNK: {
    label: 'Cyber Glitch',
    overlayClassName: 'font-bold uppercase tracking-tight',
    preview: preview('shake', 680, 1.12, 'neon'),
    inline: {
      primaryColor: assToHex('&H00FFFFFF'),
      highlightColor: assToHex('&H0000FFFF'),
      outlineColor: assToHex('&H00FF00FF'),
      outlineWidth: softenOutline(4),
      fontSize: scaleRem('2.1rem'),
      fontWeight: 700,
      fontFamily: '"Orbitron", "Outfit", sans-serif',
      backgroundColor: null,
      textTransform: 'uppercase',
    },
  },
  STORY_TELLER: {
    label: 'Storyteller',
    overlayClassName: 'font-normal',
    preview: preview('typewriter', 900, 1.02, 'cinematic'),
    inline: {
      primaryColor: assToHex('&H00E0E0E0'),
      highlightColor: assToHex('&H00E0E0E0'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: 0,
      fontSize: scaleRem('1.2rem'),
      fontWeight: 400,
      fontFamily: '"Courier New", "Courier", monospace',
      backgroundColor: null,
      textTransform: 'none',
    },
  },
  GLOW_KARAOKE: {
    label: 'Neon Karaoke',
    overlayClassName: 'font-black uppercase',
    preview: preview('fade', 760, 1.08, 'neon'),
    inline: {
      primaryColor: assToHex('&H80FFFFFF'),
      highlightColor: assToHex('&H0000FFFF'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: softenOutline(2),
      fontSize: scaleRem('1.85rem'),
      fontWeight: 800,
      fontFamily: '"Montserrat", "Outfit", sans-serif',
      backgroundColor: null,
      textTransform: 'uppercase',
    },
  },
  GLASS_MORPH: {
    label: 'Glassmorphism',
    overlayClassName: 'font-semibold',
    preview: preview('fade', 980, 1.04, 'glass', 'glass_plate'),
    inline: {
      primaryColor: assToHex('&H20FFFFFF'),
      highlightColor: assToHex('&H20FFFFFF'),
      outlineColor: assToHex('&H40000000'),
      outlineWidth: softenOutline(1),
      fontSize: scaleRem('1.2rem'),
      fontWeight: 600,
      fontFamily: '"Inter", "Outfit", sans-serif',
      backgroundColor: assToRgba('&H80FFFFFF'),
      textTransform: 'none',
    },
  },
  ALI_ABDAAL: {
    label: 'Productivity Vlog',
    overlayClassName: 'font-bold',
    preview: preview('slide_up', 840, 1.08, 'cinematic'),
    inline: {
      primaryColor: assToHex('&H00FFFFFF'),
      highlightColor: assToHex('&H0032CD32'),
      outlineColor: assToHex('&H60000000'),
      outlineWidth: 0,
      fontSize: scaleRem('1.6rem'),
      fontWeight: 700,
      fontFamily: '"Outfit", "Inter", sans-serif',
      backgroundColor: null,
      textTransform: 'none',
    },
  },
  RETRO_WAVE: {
    label: '80s Synthwave',
    overlayClassName: 'font-black uppercase tracking-[0.08em]',
    preview: preview('shake', 740, 1.15, 'neon'),
    inline: {
      primaryColor: assToHex('&H00FF00FF'),
      highlightColor: assToHex('&H0000FFFF'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: softenOutline(6),
      fontSize: scaleRem('2.1rem'),
      fontWeight: 900,
      fontFamily: '"Vampire", "Impact", sans-serif',
      backgroundColor: null,
      textTransform: 'uppercase',
    },
  },
  HACKER_TERMINAL: {
    label: 'Terminal Code',
    overlayClassName: 'font-normal uppercase',
    preview: preview('typewriter', 880, 1.03, 'terminal', 'terminal_plate'),
    inline: {
      primaryColor: assToHex('&H0000FF00'),
      highlightColor: assToHex('&H00FFFFFF'),
      outlineColor: assToHex('&H00000000'),
      outlineWidth: 0,
      fontSize: scaleRem('1.1rem'),
      fontWeight: 400,
      fontFamily: '"Consolas", "Courier New", monospace',
      backgroundColor: assToRgba('&HB0000000'),
      textTransform: 'uppercase',
    },
  },
  CINEMATIC_FILM: {
    label: 'Documentary Film',
    overlayClassName: 'font-normal tracking-[0.04em]',
    preview: preview('fade', 1100, 1.05, 'cinematic'),
    inline: {
      primaryColor: assToHex('&H00E6E6E6'),
      highlightColor: assToHex('&H00D4AF37'),
      outlineColor: assToHex('&H40000000'),
      outlineWidth: softenOutline(1),
      fontSize: scaleRem('2.5rem'),
      fontWeight: 400,
      fontFamily: '"Times New Roman", "Georgia", serif',
      backgroundColor: null,
      fontStyle: 'italic',
      textTransform: 'none',
    },
  },
} as const satisfies Record<string, SubtitleStyleDefinition>;

export const STYLE_OPTIONS = Object.keys(STYLE_REGISTRY) as Array<keyof typeof STYLE_REGISTRY>;
export type StyleName = (typeof STYLE_OPTIONS)[number];

export const ANIMATION_REGISTRY = {
  pop: {
    label: 'Pop',
    motion: {
      animationDurationMs: 820,
      animationType: 'pop',
      emphasisScale: 1.16,
    },
  },
  shake: {
    label: 'Shake',
    motion: {
      animationDurationMs: 720,
      animationType: 'shake',
      emphasisScale: 1.12,
    },
  },
  slide_up: {
    label: 'Slide Up',
    motion: {
      animationDurationMs: 760,
      animationType: 'slide_up',
      emphasisScale: 1.1,
    },
  },
  fade: {
    label: 'Fade',
    motion: {
      animationDurationMs: 980,
      animationType: 'fade',
      emphasisScale: 1.04,
    },
  },
  typewriter: {
    label: 'Typewriter',
    motion: {
      animationDurationMs: 900,
      animationType: 'typewriter',
      emphasisScale: 1.02,
    },
  },
  none: {
    label: 'None',
    motion: {
      animationDurationMs: 1000,
      animationType: 'none',
      emphasisScale: 1,
    },
  },
} as const satisfies Record<PreviewAnimationType, SubtitleAnimationDefinition>;

const EXPLICIT_ANIMATION_OPTIONS = Object.keys(ANIMATION_REGISTRY) as PreviewAnimationType[];
export const ANIMATION_OPTIONS = ['default', ...EXPLICIT_ANIMATION_OPTIONS] as const satisfies readonly SubtitleAnimationType[];

export const STYLE_LABELS: Record<StyleName, string> = Object.fromEntries(
  STYLE_OPTIONS.map((styleName) => [styleName, STYLE_REGISTRY[styleName].label]),
) as Record<StyleName, string>;

export const ANIMATION_LABELS: Record<SubtitleAnimationType, string> = {
  default: 'Preset Default',
  ...Object.fromEntries(
    EXPLICIT_ANIMATION_OPTIONS.map((animationType) => [animationType, ANIMATION_REGISTRY[animationType].label]),
  ),
} as Record<SubtitleAnimationType, string>;

export const SUBTITLE_STYLES: Record<StyleName, string> = Object.fromEntries(
  STYLE_OPTIONS.map((styleName) => [styleName, STYLE_REGISTRY[styleName].overlayClassName]),
) as Record<StyleName, string>;

export const SUBTITLE_INLINE_STYLES: Record<StyleName, SubtitleInlineStyle> = Object.fromEntries(
  STYLE_OPTIONS.map((styleName) => [styleName, STYLE_REGISTRY[styleName].inline]),
) as Record<StyleName, SubtitleInlineStyle>;

export const ANIMATION_SELECT_OPTIONS = ANIMATION_OPTIONS.map((animationType) => ({
  label: ANIMATION_LABELS[animationType],
  value: animationType,
}));

export function isStyleName(value: unknown): value is StyleName {
  return typeof value === 'string' && STYLE_OPTIONS.includes(value as StyleName);
}

export function isSubtitleAnimationType(value: unknown): value is SubtitleAnimationType {
  return typeof value === 'string' && ANIMATION_OPTIONS.includes(value as SubtitleAnimationType);
}

export function resolveSubtitleMotion(
  resolvedStyle: StyleName,
  animationType: SubtitleAnimationType = 'default',
): {
  requestedAnimationType: SubtitleAnimationType;
  resolvedAnimationType: PreviewAnimationType;
  motion: SubtitlePreviewMotion;
} {
  if (!isSubtitleAnimationType(animationType) || animationType === 'default') {
    const baseMotion = STYLE_REGISTRY[resolvedStyle].preview.motion;
    return {
      requestedAnimationType: 'default',
      resolvedAnimationType: baseMotion.animationType,
      motion: baseMotion,
    };
  }

  return {
    requestedAnimationType: animationType,
    resolvedAnimationType: animationType,
    motion: ANIMATION_REGISTRY[animationType].motion,
  };
}

export function resolveSubtitleStyle(
  styleName: string,
  animationType: SubtitleAnimationType = 'default',
): {
  inline: SubtitleInlineStyle;
  label: string;
  overlayClassName: string;
  preview: SubtitlePreviewDefinition;
  requestedAnimationType: SubtitleAnimationType;
  resolvedAnimationType: PreviewAnimationType;
  resolvedStyle: StyleName;
} {
  const resolvedStyle: StyleName = isStyleName(styleName) ? styleName : 'HORMOZI';
  const resolvedMotion = resolveSubtitleMotion(resolvedStyle, animationType);
  return {
    inline: SUBTITLE_INLINE_STYLES[resolvedStyle],
    label: STYLE_LABELS[resolvedStyle],
    overlayClassName: SUBTITLE_STYLES[resolvedStyle],
    preview: {
      bandVariant: STYLE_REGISTRY[resolvedStyle].preview.bandVariant,
      motion: resolvedMotion.motion,
      screenTheme: STYLE_REGISTRY[resolvedStyle].preview.screenTheme,
    },
    requestedAnimationType: resolvedMotion.requestedAnimationType,
    resolvedAnimationType: resolvedMotion.resolvedAnimationType,
    resolvedStyle,
  };
}

export function getSubtitleBoxStyle(
  layout: SubtitleLayout = 'single',
  surface: SubtitleSurface = 'overlay',
): CSSProperties {
  const horizontalInset = surface === 'preview' ? '9%' : '8%';
  const horizontalPadding = surface === 'preview' ? '0.35rem' : '1rem';

  if (layout === 'split') {
    return {
      left: horizontalInset,
      right: horizontalInset,
      top: surface === 'preview' ? '45%' : '45%',
      minHeight: surface === 'preview' ? '9%' : '10%',
      paddingLeft: horizontalPadding,
      paddingRight: horizontalPadding,
    };
  }

  return {
    left: horizontalInset,
    right: horizontalInset,
    bottom: surface === 'preview' ? '6.5%' : '14%',
    minHeight: surface === 'preview' ? '11%' : '14%',
    paddingLeft: horizontalPadding,
    paddingRight: horizontalPadding,
  };
}
