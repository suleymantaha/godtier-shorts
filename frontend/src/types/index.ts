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
export type SubtitleAnimationType = 'default' | 'pop' | 'shake' | 'slide_up' | 'fade' | 'typewriter' | 'none';
export type RequestedSubtitleLayout = 'auto' | 'single' | 'split';

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

export interface AuthWhoAmIResponse {
    auth_mode: 'clerk_jwt' | 'static_token';
    roles: string[];
    subject: string;
    subject_hash: string;
    token_type: 'jwt' | 'bearer';
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
    resolved_layout?: string;
    layout_fallback_reason?: string | null;
    layout_validation_status?: string;
    opening_visibility_delay_ms?: number;
    style_name?: string;
    animation_type?: SubtitleAnimationType;
    resolved_animation_type?: Exclude<SubtitleAnimationType, 'default'>;
    cut_as_short?: boolean;
    requested_duration_min?: number;
    requested_duration_max?: number;
    duration_validation_status?: string;
    tracking_quality?: {
        status?: 'good' | 'degraded' | 'fallback';
        mode?: 'tracked' | 'manual';
        total_frames?: number;
        fallback_frames?: number;
        avg_center_jump_px?: number;
        confirmed_track_frames?: number;
        grace_hold_frames?: number;
        controlled_return_frames?: number;
        reacquire_attempt_count?: number;
        reacquire_success_count?: number;
        active_track_id_switches?: number;
        shot_cut_resets?: number;
        max_track_lost_streak?: number;
        panel_swap_count?: number;
        primary_p95_center_jump_px?: number;
        secondary_p95_center_jump_px?: number;
        startup_settle_ms?: number;
        predict_fallback_active?: boolean;
        split_motion_policy?: 'stable';
    };
    transcript_quality?: {
        status?: 'good' | 'partial' | 'degraded';
        segments_without_words?: number;
        text_word_mismatches?: number;
        clamped_words_count?: number;
        reconstructed_segments_count?: number;
        empty_text_segments_after_rebuild?: number;
        avg_words_per_chunk?: number;
        max_chunk_duration?: number;
        subtitle_overflow_detected?: boolean;
        max_rendered_line_width_ratio?: number;
        safe_area_violation_count?: number;
        word_coverage_ratio?: number;
        boundary_snaps_applied?: number;
        simultaneous_event_overlap_count?: number;
        max_simultaneous_events?: number;
    };
    debug_timing?: {
        source_fps?: number;
        normalized_fps?: number;
        source_duration?: number;
        normalized_video_duration?: number;
        normalized_audio_duration?: number;
        merged_output_duration?: number;
        merged_output_drift_ms?: number;
        dropped_or_duplicated_frame_estimate?: number;
        has_audio?: boolean;
        audio_sample_rate?: number;
        audio_channels?: number;
    };
    debug_tracking?: Record<string, unknown>;
    debug_environment?: Record<string, unknown>;
    debug_artifacts?: {
        tracking_overlay?: string;
        tracking_timeline?: string;
        subtitle_chunks?: string;
        boundary_snap?: string;
        timing_report?: string;
        status?: 'complete' | 'partial';
    };
    render_quality_score?: number;
    audio_validation?: {
        has_audio?: boolean;
        audio_sample_rate?: number;
        audio_channels?: number;
        audio_duration?: number;
        audio_validation_status?: string;
    };
    subtitle_layout_quality?: {
        subtitle_overflow_detected?: boolean;
        max_rendered_line_width_ratio?: number;
        safe_area_violation_count?: number;
        lower_third_collision_detected?: boolean;
        lower_third_band_height_ratio?: number;
        resolved_safe_area_profile?: 'default' | 'lower_third_safe';
        burn_encoder?: string;
        nvenc_fallback_used?: boolean;
        nvenc_failure_reason?: string;
        overflow_strategy?: string;
        font_clamp_count?: number;
        avg_words_per_chunk?: number;
        max_chunk_duration?: number;
        chunk_count?: number;
        simultaneous_event_overlap_count?: number;
        max_simultaneous_events?: number;
    };
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
    animation_type?: SubtitleAnimationType;
    ai_engine: string;
    smoothness?: number;
    skip_subtitles?: boolean;
    num_clips?: number;
    auto_mode?: boolean;
    duration_min?: number;
    duration_max?: number;
    resolution?: string;
    layout?: RequestedSubtitleLayout;
}

export interface ManualJobPayload {
    project_id?: string;
    start_time: number;
    end_time: number;
    transcript?: Segment[] | null;
    style_name?: string;
    animation_type?: SubtitleAnimationType;
    center_x?: number;
    layout?: RequestedSubtitleLayout;
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
    animation_type?: SubtitleAnimationType;
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
    animation_type?: SubtitleAnimationType;
    layout?: RequestedSubtitleLayout;
    duration_min?: number;
    duration_max?: number;
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

export interface AccountDeletionSummary {
    deleted_projects: number;
    deleted_social_rows: number;
    cancelled_jobs: number;
    closed_websockets: number;
    scrubbed_grants: number;
}

export interface AccountDeletionResponse {
    status: 'purged';
    summary: AccountDeletionSummary;
}
