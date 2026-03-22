import { describe, expect, it } from 'vitest';

import {
  buildSubtitleChunks,
  getSubtitleChunkLines,
  planSubtitleChunkForDisplay,
} from '../../utils/subtitleTiming';

const splitLayoutOptions = {
  layout: 'split' as const,
  fontSizeRem: 2.4,
  fontWeight: 900,
};

const singleLayoutOptions = {
  layout: 'single' as const,
  fontSizeRem: 2.4,
  fontWeight: 900,
};

describe('subtitleTiming chunk planning', () => {
  it('does not extend chunk end back to segmentEnd', () => {
    const chunks = buildSubtitleChunks([
      {
        text: 'one two three four five six',
        start: 0,
        end: 4,
        words: [
          { word: 'one', start: 0, end: 0.4 },
          { word: 'two', start: 0.4, end: 0.8 },
          { word: 'three', start: 0.8, end: 1.2 },
          { word: 'four', start: 1.3, end: 1.7 },
          { word: 'five', start: 1.7, end: 2.1 },
          { word: 'six', start: 2.1, end: 2.5 },
        ],
      },
    ]);

    expect(chunks).toHaveLength(2);
    expect(chunks[0].end).toBeCloseTo(1.3, 6);
    expect(chunks[0].end).toBeLessThan(4);
  });

  it('plans split chunks with an explicit line break for wide text', () => {
    const chunks = buildSubtitleChunks([
      {
        text: 'mekanlarımızda, makamlarımızda',
        start: 0,
        end: 2,
        words: [
          { word: 'mekanlarımızda,', start: 0, end: 0.9 },
          { word: 'makamlarımızda', start: 0.95, end: 1.9 },
        ],
      },
    ], splitLayoutOptions);

    expect(chunks[0].lineBreakAfter).toBe(0);
    expect(getSubtitleChunkLines(chunks[0])).toHaveLength(2);
  });

  it('can plan preview/demo chunks for split layout without using transcript chunking', () => {
    const plan = planSubtitleChunkForDisplay([
      { word: 'Bu', start: 0, end: 0.2 },
      { word: 'bir', start: 0.2, end: 0.4 },
      { word: 'demo', start: 0.4, end: 0.6 },
      { word: 'altyazi', start: 0.6, end: 0.8 },
    ], splitLayoutOptions);

    expect(plan.lineBreakAfter).not.toBeNull();
  });
});

describe('subtitleTiming font clamps', () => {
  it('applies a split font clamp for pathological single-word chunks', () => {
    const chunks = buildSubtitleChunks([
      {
        text: 'motivasyonumuzda',
        start: 0,
        end: 1.4,
        words: [
          { word: 'motivasyonumuzda', start: 0, end: 1.4 },
        ],
      },
    ], splitLayoutOptions);

    expect(chunks[0].fontScale).toBeLessThan(1);
    expect(chunks[0].overflowStrategy).toBe('split_rechunk_1_word');
  });

  it('applies a single font clamp when conservative single layout still overflows', () => {
    const chunks = buildSubtitleChunks([
      {
        text: 'motivasyonumuzdakisorumlulugumuz',
        start: 0,
        end: 1.4,
        words: [
          { word: 'motivasyonumuzdakisorumlulugumuz', start: 0, end: 1.4 },
        ],
      },
    ], singleLayoutOptions);

    expect(chunks[0].fontScale).toBeLessThan(1);
    expect(chunks[0].overflowStrategy).toBe('single_font_clamp');
  });
});
