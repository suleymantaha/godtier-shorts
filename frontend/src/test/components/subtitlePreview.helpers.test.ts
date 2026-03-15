import { describe, expect, it } from 'vitest';

import { buildTextShadow, getSubtitlePreviewModel } from '../../components/subtitlePreview/helpers';

describe('subtitlePreview helpers', () => {
  it('returns none for zero-width non-glow shadows', () => {
    expect(buildTextShadow('#000000', 0, false)).toBe('none');
  });

  it('builds glow shadows and resolves unknown styles to HORMOZI', () => {
    expect(buildTextShadow('#ffffff', 4, true)).toContain('0 0 8px #ffffff');
    expect(getSubtitlePreviewModel('unknown').resolvedStyle).toBe('HORMOZI');
  });

  it('derives shell type and motion profile from preview state', () => {
    expect(getSubtitlePreviewModel('TIKTOK', true).shellType).toBe('phone');
    expect(getSubtitlePreviewModel('TIKTOK', false).shellType).toBe('landscape');
    expect(getSubtitlePreviewModel('HACKER_TERMINAL').motionProfile.animationType).toBe('typewriter');
    expect(getSubtitlePreviewModel('YOUTUBE_SHORT').motionProfile.animationType).toBe('pop');
    expect(getSubtitlePreviewModel('GLASS_MORPH').bandVariant).toBe('glass_plate');
    expect(getSubtitlePreviewModel('PODCAST').bandVariant).toBe('soft_plate');
    expect(getSubtitlePreviewModel('HACKER_TERMINAL').bandVariant).toBe('terminal_plate');
  });
});
