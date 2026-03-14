import type { ClipMetadata, ClipTranscriptResponse, Segment } from '../types';

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
