import { describe, expect, it } from 'vitest';

import { buildCropGuideStyle, clampCrop, findCurrentSubtitle, getCropFromClientX, getNextCropValue } from '../../components/videoOverlay/helpers';

const transcript = [
  { end: 2, start: 1, text: 'Hello', words: [] },
  { end: 4, start: 3, text: 'World', words: [] },
];

describe('videoOverlay helpers', () => {
  it('clamps crop values and computes clientX positions', () => {
    expect(clampCrop(-1)).toBe(0);
    expect(clampCrop(2)).toBe(1);
    expect(getCropFromClientX(50, { left: 0, width: 200 } as DOMRect)).toBe(0.25);
  });

  it('finds the active subtitle and keyboard crop step', () => {
    expect(findCurrentSubtitle(transcript, 1.5)?.text).toBe('Hello');
    expect(getNextCropValue(0.5, 'ArrowRight')).toBeGreaterThan(0.5);
    expect(getNextCropValue(0.5, 'Escape')).toBeNull();
  });

  it('builds crop guide styles around the center', () => {
    expect(buildCropGuideStyle(0.5)).toEqual(expect.objectContaining({
      aspectRatio: '9/16',
      maxWidth: '56.25%',
      width: 'calc(100% * 9/16 * (16/9))',
    }));
  });
});
