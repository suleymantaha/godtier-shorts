/**
 * frontend/src/types/index.ts
 * ============================
 * Proje genelinde paylaşılan TypeScript arayüzleri.
 * Hem store hem de component'lar bu dosyadan import eder.
 */

export interface LogEntry {
    message: string;
    progress: number;
    timestamp: string;
}

export type JobStatus = 'queued' | 'processing' | 'completed' | 'cancelled' | 'error' | 'empty';

export interface Job {
    job_id: string;
    url: string;
    style: string;
    status: JobStatus;
    progress: number;
    last_message: string;
    created_at: number;
    project_id?: string;
    clip_name?: string;
    output_url?: string;
    output_path?: string;
    error?: string;
    num_clips?: number;
}

export interface Clip {
    name: string;
    project?: string;
    url: string;
    has_transcript: boolean;
    ui_title?: string;
    created_at: number;
}

export interface ClipListResponse {
    clips: Clip[];
    page?: number;
    page_size?: number;
    total?: number;
    has_more?: boolean;
}

/** WhisperX kelime segmenti */
export interface Word {
    word: string;
    start: number;
    end: number;
    score?: number;
}

/** WhisperX transkript segmenti */
export interface Segment {
    text: string;
    start: number;
    end: number;
    speaker?: string;
    words: Word[];
}

export interface ViralMetadata {
    hook_text: string;
    ui_title: string;
    social_caption: string;
}

export interface RenderMetadata {
    mode?: string;
    project_id?: string;
    clip_name?: string;
    start_time?: number;
    end_time?: number;
    crop_mode?: string;
    center_x?: number | null;
    layout?: string;
    style_name?: string;
}

export interface ClipMetadata {
    transcript: Segment[];
    viral_metadata?: ViralMetadata | null;
    render_metadata?: RenderMetadata | null;
}

export type WsStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

export interface StartJobPayload {
    youtube_url: string;
    style_name: string;
    ai_engine: string;
    smoothness?: number;
    skip_subtitles?: boolean;
    num_clips?: number;
    auto_mode?: boolean;
    duration_min?: number;
    duration_max?: number;
    resolution?: string;
}

export interface ManualJobPayload {
    project_id?: string;
    start_time: number;
    end_time: number;
    transcript?: Segment[] | null;
    style_name?: string;
    center_x?: number;
    layout?: string;
}

export interface ManualCutUploadResponse {
    status: string;
    job_id: string;
    project_id: string;
    clip_name: string | null;
    output_url: string | null;
    message: string;
}

export interface ReburnPayload {
    clip_name: string;
    transcript: Segment[];
    project_id?: string;
    style_name?: string;
}

export interface BatchJobPayload {
    project_id?: string;
    start_time: number;
    end_time: number;
    num_clips: number;
    style_name: string;
    layout?: string;
}
