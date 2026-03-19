import type { Segment, Word } from '../types';
import type { SubtitleLayout } from '../config/subtitleStyles';

export const DEFAULT_MAX_WORDS_PER_SCREEN = 3;
export const DEFAULT_MAX_CHUNK_DURATION = 1.8;
export const DEFAULT_MIN_CHUNK_DURATION = 0.45;
export const DEFAULT_MAX_MERGED_CHUNK_DURATION = 2.2;
export const DEFAULT_WORD_GAP_BREAK = 0.35;
export const SMALL_GAP_BRIDGE_THRESHOLD = 0.18;
export const DEFAULT_SPLIT_MAX_WORDS_PER_SCREEN = 2;
export const SPLIT_SOFT_WRAP_RATIO = 0.92;
export const SPLIT_HARD_OVERFLOW_RATIO = 1.0;
export const SINGLE_MIN_FONT_SCALE = 0.72;
export const SPLIT_MIN_FONT_SCALE = 0.82;
export const SPLIT_FONT_CLAMP_MARGIN = 0.995;

const ZERO_WIDTH_PATTERN = /\u200b|\u200c|\u200d|\ufeff/g;
const NARROW_CHARACTERS = new Set(['i', 'l', 'ı', '!', ':', ';', "'", '|']);
const WIDE_LOWER_CHARACTERS = new Set(['m', 'w']);
const PUNCTUATION_CHARACTERS = new Set(['.', ',', '?']);
const SINGLE_MAX_TEXT_WIDTH = 844;
const SPLIT_MAX_TEXT_WIDTH = 800;

export interface SubtitleChunk {
  text: string;
  start: number;
  end: number;
  words: Word[];
  lineBreakAfter?: number | null;
  fontScale?: number;
  overflowStrategy?: string;
}

interface TimedWord extends Word {
  segmentEnd: number;
}

export interface SubtitlePlanningOptions {
  layout?: SubtitleLayout;
  fontSizeRem?: number;
  fontWeight?: number;
}

export interface ActiveSubtitleState {
  chunk: SubtitleChunk;
  activeWordIndex: number | null;
}

export function normalizeSubtitleText(text: string): string {
  return text
    .normalize('NFC')
    .replace(ZERO_WIDTH_PATTERN, '')
    .replaceAll('…', '...')
    .replaceAll('’', "'")
    .replaceAll('–', '-')
    .replaceAll('—', '-')
    .replace(/\s+/g, ' ')
    .trim();
}

export function buildSubtitleChunks(transcript: Segment[], options: SubtitlePlanningOptions = {}): SubtitleChunk[] {
  const layout = options.layout ?? 'single';
  const words = collectValidWords(transcript);
  if (words.length === 0) {
    return transcript
      .filter((segment) => Number.isFinite(segment.start) && Number.isFinite(segment.end) && segment.end > segment.start)
      .map((segment) => ({
        text: segment.text,
        start: segment.start,
        end: segment.end,
        words: buildWordsFromSegmentText(segment),
        lineBreakAfter: null,
      }));
  }

  const seededChunks = chunkWords(words, layout === 'split' ? DEFAULT_SPLIT_MAX_WORDS_PER_SCREEN : DEFAULT_MAX_WORDS_PER_SCREEN);
  const planned = layout === 'split'
    ? applySplitChunkPlanning(seededChunks, options)
    : applySingleChunkPlanning(seededChunks, options);

  return planned.chunks.map((chunk, index) => ({
    text: chunk.map((word) => word.word).join(' ').trim(),
    start: chunk[0].start,
    end: resolveChunkEnd(chunk, planned.chunks[index + 1]),
    words: chunk,
    lineBreakAfter: planned.lineBreaks.get(index) ?? null,
    fontScale: planned.fontScales.get(index),
    overflowStrategy: planned.overflowStrategy === 'default' ? undefined : planned.overflowStrategy,
  }));
}

export function findActiveSubtitleState(
  transcript: Segment[],
  currentTime: number,
  options: SubtitlePlanningOptions = {},
): ActiveSubtitleState | null {
  const chunks = buildSubtitleChunks(transcript, options);
  const activeChunk = chunks.find((chunk) => currentTime >= chunk.start && currentTime <= chunk.end);
  if (!activeChunk) {
    return null;
  }

  const activeWordIndex = activeChunk.words.findIndex((word) => currentTime >= word.start && currentTime <= word.end);
  return {
    chunk: activeChunk,
    activeWordIndex: activeWordIndex >= 0 ? activeWordIndex : null,
  };
}

export function getSubtitleChunkLines(chunk: Pick<SubtitleChunk, 'words' | 'lineBreakAfter'>): Word[][] {
  if (chunk.lineBreakAfter === null || chunk.lineBreakAfter === undefined || chunk.lineBreakAfter < 0 || chunk.lineBreakAfter >= chunk.words.length - 1) {
    return [chunk.words];
  }
  return [chunk.words.slice(0, chunk.lineBreakAfter + 1), chunk.words.slice(chunk.lineBreakAfter + 1)];
}

export function planSubtitleChunkForDisplay(
  words: Word[],
  options: SubtitlePlanningOptions = {},
): Pick<SubtitleChunk, 'lineBreakAfter' | 'overflowStrategy' | 'words' | 'fontScale'> {
  if ((options.layout ?? 'single') !== 'split') {
    return {
      words,
      lineBreakAfter: null,
    };
  }

  const timedWords: TimedWord[] = words.map((word, index) => ({
    ...word,
    segmentEnd: word.end ?? (index + 1) * 0.24,
  }));
  const singleLineRatio = estimateLineWidthRatio(timedWords, options);
  if (singleLineRatio <= SPLIT_SOFT_WRAP_RATIO) {
    return {
      words,
      lineBreakAfter: null,
    };
  }

  const { breakAfter, widestRatio } = resolveSplitLineBreakAfter(timedWords, options);
  return {
    words,
    lineBreakAfter: breakAfter,
    fontScale: resolveSplitChunkFontScale(timedWords, {
      breakAfter,
      options,
    }),
    overflowStrategy: widestRatio > SPLIT_HARD_OVERFLOW_RATIO ? 'split_rechunk_1_word' : 'split_line_break',
  };
}

function collectValidWords(transcript: Segment[]): TimedWord[] {
  const words = transcript
    .flatMap((segment) => (segment.words ?? []).map((word) => ({ ...word, segmentEnd: segment.end })))
    .filter((word): word is TimedWord => Boolean(word?.word) && Number.isFinite(word?.start) && Number.isFinite(word?.end) && word.end > word.start)
    .map((word) => ({
      word: word.word,
      start: word.start,
      end: word.end,
      score: word.score,
      segmentEnd: word.segmentEnd,
    }))
    .sort((left, right) => left.start - right.start);

  return resolveOverlaps(words);
}

function buildWordsFromSegmentText(segment: Segment): TimedWord[] {
  const text = segment.text.trim();
  if (!text || segment.end <= segment.start) {
    return [];
  }

  const tokens = text.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) {
    return [];
  }

  const totalDuration = Math.max(segment.end - segment.start, 0.01);
  const wordDuration = totalDuration / tokens.length;
  return tokens.map((token, index) => ({
    word: token,
    start: segment.start + (index * wordDuration),
    end: index === tokens.length - 1 ? segment.end : segment.start + ((index + 1) * wordDuration),
    score: 1,
    segmentEnd: segment.end,
  }));
}

function resolveOverlaps(words: TimedWord[]): TimedWord[] {
  const resolved: TimedWord[] = [];
  for (const word of words) {
    const normalized = { ...word };
    if (resolved.length > 0) {
      const previous = resolved[resolved.length - 1];
      if (normalized.start < previous.end) {
        previous.end = Math.max(previous.start + 0.01, normalized.start);
        normalized.start = Math.max(normalized.start, previous.end);
        if (normalized.end <= normalized.start) {
          normalized.end = normalized.start + 0.01;
        }
      }
    }
    resolved.push(normalized);
  }
  return resolved;
}

function chunkWords(words: TimedWord[], maxWords = DEFAULT_MAX_WORDS_PER_SCREEN): TimedWord[][] {
  const chunks: TimedWord[][] = [];
  let currentChunk: TimedWord[] = [];

  for (let index = 0; index < words.length; index += 1) {
    const word = words[index];
    currentChunk.push(word);
    const nextWord = words[index + 1];
    const timeGap = nextWord ? nextWord.start - word.end : 0;
    const chunkDuration = currentChunk[currentChunk.length - 1].end - currentChunk[0].start;
    const normalized = normalizeSubtitleText(word.word);
    const hasStrongPunctuation = /[.!?]/.test(normalized);
    const hasWeakPunctuation = /[,;:]/.test(normalized);

    const shouldBreak = currentChunk.length >= maxWords
      || chunkDuration >= DEFAULT_MAX_CHUNK_DURATION
      || timeGap > DEFAULT_WORD_GAP_BREAK
      || hasStrongPunctuation
      || (hasWeakPunctuation && currentChunk.length >= 2);

    if (shouldBreak) {
      chunks.push(currentChunk);
      currentChunk = [];
    }
  }

  if (currentChunk.length > 0) {
    chunks.push(currentChunk);
  }

  return mergeShortChunks(chunks);
}

function mergeShortChunks(chunks: TimedWord[][]): TimedWord[][] {
  const merged: TimedWord[][] = [];
  let pending: TimedWord[] | null = null;

  for (const chunk of chunks) {
    let current = [...chunk];
    if (pending) {
      const combined = [...pending, ...current];
      if (!/[.!?]/.test(normalizeSubtitleText(pending[pending.length - 1].word))
        && getChunkDuration(combined) <= DEFAULT_MAX_MERGED_CHUNK_DURATION) {
        current = combined;
        pending = null;
      } else {
        merged.push(pending);
        pending = null;
      }
    }

    if (getChunkDuration(current) < DEFAULT_MIN_CHUNK_DURATION) {
      pending = current;
      continue;
    }
    merged.push(current);
  }

  if (pending) {
    if (merged.length > 0) {
      const last = merged[merged.length - 1];
      const combined = [...last, ...pending];
      if (!/[.!?]/.test(normalizeSubtitleText(last[last.length - 1].word))
        && getChunkDuration(combined) <= DEFAULT_MAX_MERGED_CHUNK_DURATION) {
        merged[merged.length - 1] = combined;
      } else {
        merged.push(pending);
      }
    } else {
      merged.push(pending);
    }
  }

  return merged;
}

function getChunkDuration(chunk: TimedWord[]): number {
  if (chunk.length === 0) {
    return 0;
  }
  return Math.max(0, chunk[chunk.length - 1].end - chunk[0].start);
}

function resolveChunkEnd(chunk: TimedWord[], nextChunk?: TimedWord[]): number {
  const tailEnd = chunk[chunk.length - 1]?.end ?? 0;
  if (!nextChunk || nextChunk.length === 0) {
    return tailEnd;
  }
  const nextStart = nextChunk[0]?.start ?? tailEnd;
  const gap = nextStart - tailEnd;
  if (gap >= 0 && gap < SMALL_GAP_BRIDGE_THRESHOLD) {
    return nextStart;
  }
  return tailEnd;
}

function applySplitChunkPlanning(
  chunks: TimedWord[][],
  options: SubtitlePlanningOptions,
): {
  chunks: TimedWord[][];
  lineBreaks: Map<number, number>;
  fontScales: Map<number, number>;
  overflowStrategy: string;
} {
  const plannedChunks: TimedWord[][] = [];
  const lineBreaks = new Map<number, number>();
  const fontScales = new Map<number, number>();
  let overflowStrategy = 'default';

  for (const chunk of chunks) {
    if (chunk.length === 0) {
      continue;
    }

    const singleLineRatio = estimateLineWidthRatio(chunk, options);
    if (singleLineRatio <= SPLIT_SOFT_WRAP_RATIO) {
      plannedChunks.push(chunk);
      continue;
    }

    const { breakAfter, widestRatio } = resolveSplitLineBreakAfter(chunk, options);
    if (breakAfter !== null && widestRatio <= SPLIT_HARD_OVERFLOW_RATIO) {
      lineBreaks.set(plannedChunks.length, breakAfter);
      plannedChunks.push(chunk);
      overflowStrategy = promoteOverflowStrategy(overflowStrategy, 'split_line_break');
      continue;
    }

    plannedChunks.push(...chunk.map((word) => [word]));
    overflowStrategy = promoteOverflowStrategy(overflowStrategy, 'split_rechunk_1_word');
  }

  plannedChunks.forEach((chunk, index) => {
    const fontScale = resolveSplitChunkFontScale(chunk, {
      breakAfter: lineBreaks.get(index) ?? null,
      options,
    });
    if (fontScale < 0.9999) {
      fontScales.set(index, fontScale);
    }
  });

  return {
    chunks: plannedChunks,
    lineBreaks,
    fontScales,
    overflowStrategy,
  };
}

function applySingleChunkPlanning(
  chunks: TimedWord[][],
  options: SubtitlePlanningOptions,
): {
  chunks: TimedWord[][];
  lineBreaks: Map<number, number>;
  fontScales: Map<number, number>;
  overflowStrategy: string;
} {
  let plannedChunks = chunks;
  let lineBreaks = new Map<number, number>();
  let fontScales = new Map<number, number>();
  let overflowStrategy = 'default';

  let overflow = estimateChunkOverflow(plannedChunks, lineBreaks, fontScales, options);
  if (overflow.subtitle_overflow_detected) {
    plannedChunks = chunkWords(plannedChunks.flat(), 2);
    lineBreaks = new Map<number, number>();
    fontScales = new Map<number, number>();
    overflowStrategy = promoteOverflowStrategy(overflowStrategy, 'rechunk_2_words');
    overflow = estimateChunkOverflow(plannedChunks, lineBreaks, fontScales, options);
  }

  if (overflow.subtitle_overflow_detected) {
    lineBreaks = resolveConservativeLineBreaks(plannedChunks);
    overflowStrategy = promoteOverflowStrategy(overflowStrategy, 'conservative_line_break');
    overflow = estimateChunkOverflow(plannedChunks, lineBreaks, fontScales, options);
  }

  if (overflow.subtitle_overflow_detected) {
    fontScales = resolveChunkFontScales(plannedChunks, lineBreaks, options, SINGLE_MIN_FONT_SCALE);
    if (fontScales.size > 0) {
      overflowStrategy = promoteOverflowStrategy(overflowStrategy, 'single_font_clamp');
    }
  }

  return {
    chunks: plannedChunks,
    lineBreaks,
    fontScales,
    overflowStrategy,
  };
}

function resolveSplitLineBreakAfter(
  chunk: TimedWord[],
  options: SubtitlePlanningOptions,
): {
  breakAfter: number | null;
  widestRatio: number;
} {
  if (chunk.length < 2) {
    return {
      breakAfter: null,
      widestRatio: estimateLineWidthRatio(chunk, options),
    };
  }

  let bestBreakAfter: number | null = null;
  let bestWidestRatio = Number.POSITIVE_INFINITY;

  for (let index = 0; index < chunk.length - 1; index += 1) {
    const widestRatio = Math.max(
      estimateLineWidthRatio(chunk.slice(0, index + 1), options),
      estimateLineWidthRatio(chunk.slice(index + 1), options),
    );
    if (widestRatio < bestWidestRatio) {
      bestBreakAfter = index;
      bestWidestRatio = widestRatio;
    }
  }

  return {
    breakAfter: bestBreakAfter,
    widestRatio: bestWidestRatio,
  };
}

function estimateLineWidthRatio(words: TimedWord[], options: SubtitlePlanningOptions): number {
  return estimateLineWidthRatioWithScale(words, options, 1);
}

function estimateLineWidthRatioWithScale(
  words: TimedWord[],
  options: SubtitlePlanningOptions,
  fontScale: number,
): number {
  const text = words.map((word) => word.word.trim()).filter(Boolean).join(' ');
  const normalized = normalizeSubtitleText(text);
  if (!normalized) {
    return 0;
  }

  const layout = options.layout ?? 'single';
  const fontSizeUnits = resolveLogicalFontSize(options, layout);
  let estimatedWidth = estimateTextUnits(normalized) * fontSizeUnits * Math.max(fontScale, 0);
  if ((options.fontWeight ?? 700) >= 800) {
    estimatedWidth *= 1.05;
  }

  return estimatedWidth / (layout === 'split' ? SPLIT_MAX_TEXT_WIDTH : SINGLE_MAX_TEXT_WIDTH);
}

function resolveLogicalFontSize(options: SubtitlePlanningOptions, layout: SubtitleLayout): number {
  const baseFontSize = Math.max(28, Math.round((options.fontSizeRem ?? 2.4) * 50));
  if (layout === 'split') {
    return Math.max(28, Math.round(baseFontSize * 0.88));
  }
  return baseFontSize;
}

function resolveSplitChunkFontScale(
  chunk: TimedWord[],
  {
    breakAfter,
    options,
  }: {
    breakAfter: number | null;
    options: SubtitlePlanningOptions;
  },
): number {
  const lines = breakAfter === null || breakAfter < 0 || breakAfter >= chunk.length - 1
    ? [chunk]
    : [chunk.slice(0, breakAfter + 1), chunk.slice(breakAfter + 1)];
  const widestRatio = Math.max(
    ...lines.map((line) => estimateLineWidthRatioWithScale(line, options, 1)),
  );
  if (widestRatio <= 1) {
    return 1;
  }
  const desiredScale = (1 / widestRatio) * SPLIT_FONT_CLAMP_MARGIN;
  return Math.min(1, Math.max(SPLIT_MIN_FONT_SCALE, Number(desiredScale.toFixed(4))));
}

function resolveChunkFontScales(
  chunks: TimedWord[][],
  lineBreaks: Map<number, number>,
  options: SubtitlePlanningOptions,
  minScale: number,
): Map<number, number> {
  const fontScales = new Map<number, number>();
  chunks.forEach((chunk, index) => {
    const breakAfter = lineBreaks.get(index) ?? null;
    const lines = breakAfter === null || breakAfter < 0 || breakAfter >= chunk.length - 1
      ? [chunk]
      : [chunk.slice(0, breakAfter + 1), chunk.slice(breakAfter + 1)];
    const widestRatio = Math.max(
      ...lines.map((line) => estimateLineWidthRatioWithScale(line, options, 1)),
    );
    if (widestRatio <= 1) {
      return;
    }
    const desiredScale = (1 / widestRatio) * SPLIT_FONT_CLAMP_MARGIN;
    const scale = Math.min(1, Math.max(minScale, Number(desiredScale.toFixed(4))));
    if (scale < 0.9999) {
      fontScales.set(index, scale);
    }
  });
  return fontScales;
}

function resolveConservativeLineBreaks(chunks: TimedWord[][]): Map<number, number> {
  const lineBreaks = new Map<number, number>();
  chunks.forEach((chunk, index) => {
    if (chunk.length < 2) {
      return;
    }
    lineBreaks.set(index, Math.max(0, Math.floor(chunk.length / 2) - 1));
  });
  return lineBreaks;
}

function estimateChunkOverflow(
  chunks: TimedWord[][],
  lineBreaks: Map<number, number>,
  fontScales: Map<number, number>,
  options: SubtitlePlanningOptions,
): {
  subtitle_overflow_detected: boolean;
  max_rendered_line_width_ratio: number;
  safe_area_violation_count: number;
} {
  let maxRatio = 0;
  let safeAreaViolations = 0;
  chunks.forEach((chunk, index) => {
    if (chunk.length === 0) {
      return;
    }
    const breakAfter = lineBreaks.get(index);
    const lines = breakAfter === undefined || breakAfter < 0 || breakAfter >= chunk.length - 1
      ? [chunk]
      : [chunk.slice(0, breakAfter + 1), chunk.slice(breakAfter + 1)];
    const fontScale = fontScales.get(index) ?? 1;
    const widest = Math.max(...lines.map((line) => estimateLineWidthRatioWithScale(line, options, fontScale)));
    maxRatio = Math.max(maxRatio, widest);
    if (widest > 1) {
      safeAreaViolations += 1;
    }
  });
  return {
    subtitle_overflow_detected: safeAreaViolations > 0,
    max_rendered_line_width_ratio: maxRatio,
    safe_area_violation_count: safeAreaViolations,
  };
}

function estimateTextUnits(normalized: string): number {
  let units = 0;
  for (const char of normalized) {
    if (char.trim() === '') {
      units += 0.28;
    } else if (NARROW_CHARACTERS.has(char)) {
      units += 0.34;
    } else if (PUNCTUATION_CHARACTERS.has(char)) {
      units += 0.26;
    } else if (/\d/.test(char)) {
      units += 0.52;
    } else if (WIDE_LOWER_CHARACTERS.has(char)) {
      units += 0.62;
    } else if (char.toLowerCase() !== char.toUpperCase()) {
      units += char === char.toUpperCase() ? 0.58 : 0.49;
    } else {
      units += 0.49;
    }
  }
  return units;
}

function promoteOverflowStrategy(current: string, candidate: string): string {
  const priority: Record<string, number> = {
    default: 0,
    rechunk_2_words: 1,
    conservative_line_break: 2,
    single_font_clamp: 3,
    split_line_break: 4,
    split_rechunk_1_word: 5,
  };
  return (priority[candidate] ?? 0) >= (priority[current] ?? 0) ? candidate : current;
}
