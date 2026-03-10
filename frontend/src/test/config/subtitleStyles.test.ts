import { describe, it, expect } from 'vitest';
import { SUBTITLE_STYLES, SUBTITLE_INLINE_STYLES, STYLE_OPTIONS, type StyleName } from '../../config/subtitleStyles';

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

  it('correctly converts ASS colors to CSS hex', () => {
    const lower = (s: string) => s.toLowerCase();
    expect(lower(SUBTITLE_INLINE_STYLES.HORMOZI.primaryColor)).toBe('#ffffff');
    expect(lower(SUBTITLE_INLINE_STYLES.HORMOZI.highlightColor)).toBe('#ffff00');
    expect(lower(SUBTITLE_INLINE_STYLES.TIKTOK.highlightColor)).toBe('#ff00ff');
    expect(lower(SUBTITLE_INLINE_STYLES.MRBEAST.highlightColor)).toBe('#00ff00');
  });

  it('exports STYLE_OPTIONS as a readonly array', () => {
    expect(STYLE_OPTIONS.length).toBeGreaterThan(0);
    expect(STYLE_OPTIONS).toContain('HORMOZI');
    expect(STYLE_OPTIONS).toContain('MINIMALIST');
  });

  it('StyleName type matches STYLE_OPTIONS values', () => {
    const names: StyleName[] = [...STYLE_OPTIONS];
    expect(names.length).toBe(STYLE_OPTIONS.length);
  });
});
