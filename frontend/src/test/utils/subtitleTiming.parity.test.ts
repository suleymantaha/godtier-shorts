import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { buildSubtitleChunks } from '../../utils/subtitleTiming';

type ParityCase = {
  name: string;
  layout: 'single' | 'split';
  font_size_rem: number;
  font_weight: number;
  transcript: Array<{
    end: number;
    start: number;
    text: string;
    words: Array<{ end: number; start: number; word: string }>;
  }>;
  expected: {
    overflow_strategy: string;
    chunks: Array<{
      text: string;
      line_break_after?: number;
      font_scale_below?: number;
    }>;
  };
};

const fixturePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../../tests/fixtures/subtitle_parity_cases.json',
);
const parityCases = JSON.parse(readFileSync(fixturePath, 'utf8')) as ParityCase[];

describe('subtitleTiming parity contract', () => {
  it.each(parityCases)('$name', (testCase) => {
    const chunks = buildSubtitleChunks(testCase.transcript, {
      layout: testCase.layout,
      fontSizeRem: testCase.font_size_rem,
      fontWeight: testCase.font_weight,
    });

    expect(chunks).toHaveLength(testCase.expected.chunks.length);
    expect(chunks[0]?.overflowStrategy).toBe(testCase.expected.overflow_strategy);

    for (const [index, expectedChunk] of testCase.expected.chunks.entries()) {
      const actualChunk = chunks[index];
      expect(actualChunk?.text).toBe(expectedChunk.text);
      if (expectedChunk.line_break_after !== undefined) {
        expect(actualChunk?.lineBreakAfter).toBe(expectedChunk.line_break_after);
      }
      if (expectedChunk.font_scale_below !== undefined) {
        expect(actualChunk?.fontScale ?? 1).toBeLessThan(expectedChunk.font_scale_below);
      }
    }
  });
});
