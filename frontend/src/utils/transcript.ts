import type { ClipMetadata, ClipTranscriptResponse, Segment, Word } from '../types';

function tokenizeTranscriptText(text: string): string[] {
  return text.trim().split(/\s+/).filter(Boolean);
}

function isFiniteWord(word: Word | undefined): word is Word {
  if (!word) {
    return false;
  }

  return Number.isFinite(word.start)
    && Number.isFinite(word.end)
    && word.end > word.start
    && Boolean(word.word?.trim());
}

function buildSegmentWords(text: string, start: number, end: number): Word[] {
  const tokens = tokenizeTranscriptText(text);
  if (tokens.length === 0 || end <= start) {
    return [];
  }

  const totalDuration = Math.max(end - start, 0.01);
  const wordDuration = totalDuration / tokens.length;
  return tokens.map((token, index) => ({
    word: token,
    start: start + (index * wordDuration),
    end: index === tokens.length - 1 ? end : start + ((index + 1) * wordDuration),
    score: 1,
  }));
}

export function syncSegmentTextAndWords(segment: Segment, text: string): Segment {
  const nextText = text;
  const tokens = tokenizeTranscriptText(nextText);
  const validWords = (segment.words ?? []).filter(isFiniteWord);

  if (tokens.length === 0 || segment.end <= segment.start) {
    return {
      ...segment,
      text: nextText,
      words: [],
    };
  }

  if (validWords.length === tokens.length) {
    return {
      ...segment,
      text: nextText,
      words: validWords.map((word, index) => ({
        ...word,
        word: tokens[index],
      })),
    };
  }

  return {
    ...segment,
    text: nextText,
    words: buildSegmentWords(nextText, segment.start, segment.end),
  };
}

/**
 * API'den gelen transcript verisini Segment[] formatına normalize eder.
 * transcript doğrudan dizi veya { transcript: Segment[] } içinde gelebilir.
 */
export function normalizeTranscript(
  data: { transcript?: Segment[] | ClipMetadata } | ClipTranscriptResponse
): Segment[] {
  const t = data.transcript;
  if (Array.isArray(t)) return t;
  if (t && typeof t === 'object' && Array.isArray((t as ClipMetadata).transcript)) {
    return (t as ClipMetadata).transcript;
  }
  return [];
}
