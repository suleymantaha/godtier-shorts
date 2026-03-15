import type { Segment, Word } from '../types';

export const DEFAULT_MAX_WORDS_PER_SCREEN = 3;
export const DEFAULT_MAX_CHUNK_DURATION = 1.8;
export const DEFAULT_MIN_CHUNK_DURATION = 0.45;
export const DEFAULT_MAX_MERGED_CHUNK_DURATION = 2.2;
export const DEFAULT_WORD_GAP_BREAK = 0.35;

const ZERO_WIDTH_PATTERN = /\u200b|\u200c|\u200d|\ufeff/g;

export interface SubtitleChunk {
  text: string;
  start: number;
  end: number;
  words: Word[];
}

interface TimedWord extends Word {
  segmentEnd: number;
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

export function buildSubtitleChunks(transcript: Segment[]): SubtitleChunk[] {
  const words = collectValidWords(transcript);
  if (words.length === 0) {
    return transcript
      .filter((segment) => Number.isFinite(segment.start) && Number.isFinite(segment.end) && segment.end > segment.start)
      .map((segment) => ({
        text: segment.text,
        start: segment.start,
        end: segment.end,
        words: buildWordsFromSegmentText(segment),
      }));
  }

  return chunkWords(words).map((chunk) => ({
    text: chunk.map((word) => word.word).join(' ').trim(),
    start: chunk[0].start,
    end: Math.max(chunk[chunk.length - 1].end, ...chunk.map((word) => word.segmentEnd ?? word.end)),
    words: chunk,
  }));
}

export function findActiveSubtitleState(transcript: Segment[], currentTime: number): ActiveSubtitleState | null {
  const chunks = buildSubtitleChunks(transcript);
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

function chunkWords(words: TimedWord[]): TimedWord[][] {
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

    const shouldBreak = currentChunk.length >= DEFAULT_MAX_WORDS_PER_SCREEN
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
