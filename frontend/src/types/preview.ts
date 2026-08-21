export interface PreviewSource {
  video_id: string;
  title: string;
  duration_seconds: number;
  thumbnail_url: string | null;
}

export interface PreviewTranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface ViralCandidate {
  start_time: number;
  end_time: number;
  ui_title?: string;
  hook_text?: string;
  viral_score?: number;
}

export interface PreviewAnalyzeResponse {
  source: PreviewSource;
  transcript: PreviewTranscriptSegment[];
  transcript_source: 'captions' | 'limited_transcription';
  candidates: ViralCandidate[];
  preview_mode: 'browser';
}
