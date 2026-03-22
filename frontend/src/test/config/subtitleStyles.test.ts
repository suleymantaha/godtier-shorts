import { describe, expect, it } from 'vitest';

import {
  STYLE_OPTIONS,
  SUBTITLE_INLINE_STYLES,
  SUBTITLE_STYLES,
  getStyleLabel,
  getSubtitleBoxStyle,
  resolveSubtitleStyle,
  type StyleName,
} from '../../config/subtitleStyles';

describe('subtitleStyles', () => {
  it('has a style entry for every STYLE_OPTIONS member', () => {
    for (const name of STYLE_OPTIONS) {
      expect(SUBTITLE_STYLES[name]).toBeDefined();
      expect(typeof SUBTITLE_STYLES[name]).toBe('string');
      expect(SUBTITLE_STYLES[name].length).toBeGreaterThan(0);
    }
  });

  it('has an inline style entry for every STYLE_OPTIONS member', () => {
    for (const name of STYLE_OPTIONS) {
      const style = SUBTITLE_INLINE_STYLES[name];
      expect(style).toBeDefined();
      expect(style.primaryColor).toBeTruthy();
      expect(style.highlightColor).toBeTruthy();
      expect(style.fontSize).toBeTruthy();
      expect(typeof style.fontWeight).toBe('number');
      expect(typeof style.outlineWidth).toBe('number');
    }
  });

  it('correctly converts ASS colors to CSS hex via registry output', () => {
    const lower = (s: string) => s.toLowerCase();
    expect(lower(SUBTITLE_INLINE_STYLES.HORMOZI.primaryColor)).toBe('#ffffff');
    expect(lower(SUBTITLE_INLINE_STYLES.HORMOZI.highlightColor)).toBe('#ffff00');
    expect(lower(SUBTITLE_INLINE_STYLES.TIKTOK.highlightColor)).toBe('#ff00ff');
    expect(lower(SUBTITLE_INLINE_STYLES.MRBEAST.highlightColor)).toBe('#00ff00');
  });

  it('exports STYLE_OPTIONS without CUSTOM and keeps StyleName aligned', () => {
    expect(STYLE_OPTIONS.length).toBeGreaterThan(0);
    expect(STYLE_OPTIONS).toContain('HORMOZI');
    expect(STYLE_OPTIONS).toContain('MINIMALIST');
    expect(STYLE_OPTIONS).not.toContain('CUSTOM');

    const names: StyleName[] = [...STYLE_OPTIONS];
    expect(names.length).toBe(STYLE_OPTIONS.length);
  });

  it('derives labels and safe area metrics from one source of truth', () => {
    expect(getStyleLabel('HIGHCARE')).toBe('High Contrast');
    expect(resolveSubtitleStyle('unknown').resolvedStyle).toBe('HORMOZI');
    expect(getSubtitleBoxStyle('single').bottom).toBe('14%');
    expect(getSubtitleBoxStyle('single', 'overlay', 'lower_third_safe').bottom).toBe('22%');
    expect(getSubtitleBoxStyle('split').top).toBe('45%');
    expect(getSubtitleBoxStyle('split').minHeight).toBe('10.5%');
    expect(getSubtitleBoxStyle('single', 'preview').bottom).toBe('6.5%');
    expect(getSubtitleBoxStyle('single', 'preview', 'lower_third_safe').bottom).toBe('10.5%');
    expect(getSubtitleBoxStyle('single', 'preview').minHeight).toBe('11%');
    expect(getSubtitleBoxStyle('split', 'preview').minHeight).toBe('9.5%');
  });

  it('exposes preview motion metadata for every selectable style', () => {
    for (const name of STYLE_OPTIONS) {
      const resolved = resolveSubtitleStyle(name);
      expect(resolved.preview.motion.animationDurationMs).toBeGreaterThan(0);
      expect(resolved.preview.motion.emphasisScale).toBeGreaterThanOrEqual(1);
      expect(resolved.preview.motion.animationType).toBeTruthy();
      expect(resolved.preview.screenTheme).toBeTruthy();
      expect(resolved.preview.bandVariant).toBeTruthy();
    }
  });

  it('keeps special preview variants for background-based styles', () => {
    expect(resolveSubtitleStyle('YOUTUBE_SHORT').preview.motion.animationType).toBe('pop');
    expect(resolveSubtitleStyle('YOUTUBE_SHORT').preview.bandVariant).toBe('bold_plate');
    expect(resolveSubtitleStyle('PODCAST').preview.bandVariant).toBe('soft_plate');
    expect(resolveSubtitleStyle('GLASS_MORPH').preview.bandVariant).toBe('glass_plate');
    expect(resolveSubtitleStyle('HACKER_TERMINAL').preview.bandVariant).toBe('terminal_plate');
  });
});
