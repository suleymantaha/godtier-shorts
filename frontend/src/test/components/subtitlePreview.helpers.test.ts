import { describe, expect, it } from 'vitest';

import { buildTextShadow, getSubtitlePreviewModel } from '../../components/subtitlePreview/helpers';

describe('subtitlePreview helpers', () => {
  it('returns none for zero-width non-glow shadows', () => {
    expect(buildTextShadow('#000000', 0, false)).toBe('none');
  });

  it('builds glow shadows and resolves unknown styles to HORMOZI', () => {
    expect(buildTextShadow('#ffffff', 4, true)).toContain('0 0 10px #ffffff');
    expect(getSubtitlePreviewModel('unknown').resolvedStyle).toBe('HORMOZI');
  });
});
