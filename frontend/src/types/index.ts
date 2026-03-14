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

export interface DeleteClipResponse {
    status: 'deleted' | 'not_found';
    deleted: boolean;
    project_id: string;
    clip_name: string;
}

/** Kelime zaman damgalı transkript segmenti */
export interface Word {
    word: string;
    start: number;
    end: number;
    score?: number;
}

/** Ana transkript segmenti */
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
    cut_as_short?: boolean;
}

export interface ClipMetadata {
    transcript: Segment[];
    viral_metadata?: ViralMetadata | null;
    render_metadata?: RenderMetadata | null;
}

export type TranscriptStatus = 'ready' | 'pending' | 'failed';
export type ClipTranscriptStatus = 'ready' | 'project_pending' | 'recovering' | 'needs_recovery' | 'failed';
export type TranscriptRecoveryStrategy = 'auto' | 'project_slice' | 'transcribe_source';

export interface ClipTranscriptCapabilities {
    has_clip_metadata: boolean;
    has_clip_transcript: boolean;
    has_raw_backup: boolean;
    project_has_transcript: boolean;
    can_recover_from_project: boolean;
    can_transcribe_source: boolean;
    resolved_project_id?: string | null;
}

export interface ClipTranscriptResponse {
    transcript: Segment[];
    viral_metadata?: ViralMetadata | null;
    render_metadata?: RenderMetadata | null;
    capabilities?: ClipTranscriptCapabilities;
    transcript_status?: ClipTranscriptStatus;
    recommended_strategy?: Exclude<TranscriptRecoveryStrategy, 'auto'> | null;
    active_job_id?: string | null;
    last_error?: string | null;
}

export interface ProjectTranscriptResponse {
    transcript: Segment[];
    transcript_status?: TranscriptStatus;
    active_job_id?: string | null;
    last_error?: string | null;
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

export interface ClipTranscriptRecoveryPayload {
    clip_name: string;
    project_id?: string;
    strategy: TranscriptRecoveryStrategy;
}

export interface ProjectTranscriptRecoveryPayload {
    project_id: string;
}

export interface ProjectSummary {
    id: string;
    has_master: boolean;
    has_transcript: boolean;
    transcript_status?: TranscriptStatus;
    active_job_id?: string | null;
    last_error?: string | null;
}

export interface BatchJobPayload {
    project_id?: string;
    start_time: number;
    end_time: number;
    num_clips: number;
    style_name: string;
    layout?: string;
}

export type SocialPlatform =
    | 'youtube_shorts'
    | 'tiktok'
    | 'instagram_reels'
    | 'facebook_reels'
    | 'x'
    | 'linkedin';

export interface SocialAccount {
    id: string;
    name: string;
    platform: SocialPlatform;
    provider?: string;
    username?: string | null;
    avatar_url?: string | null;
}

export interface ShareDraftContent {
    title: string;
    text: string;
    hashtags: string[];
    hook_text?: string;
    viral_score?: number;
}

export interface SharePrefillResponse {
    project_id: string;
    clip_name: string;
    clip_exists: boolean;
    source: {
        viral_metadata?: ViralMetadata | null;
        has_clip_metadata: boolean;
        has_drafts: boolean;
    };
    platforms: Record<SocialPlatform, ShareDraftContent>;
}

export interface PublishJob {
    id: string;
    provider: string;
    project_id: string;
    clip_name: string;
    platform: SocialPlatform;
    account_id: string;
    mode: 'now' | 'scheduled';
    state: 'draft' | 'queued' | 'scheduled' | 'publishing' | 'published' | 'retrying' | 'failed' | 'cancelled' | 'pending_approval';
    attempts: number;
    scheduled_at?: string | null;
    last_error?: string | null;
    provider_job_id?: string | null;
    approval_required: boolean;
    timeline?: Array<{ state: string; message: string; at: string }>;
    created_at: string;
    updated_at: string;
}
