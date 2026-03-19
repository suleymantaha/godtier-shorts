# Deep Scan Appendix (Per-File Catalog)

## Backend Files
### `backend/__init__.py`
- Module: `backend.__init__`
- Purpose: (docstring not found)
- Public symbols: (none detected)
- Internal dependencies (0): (none)
- Used by (0): (none detected)

### `backend/api/__init__.py`
- Module: `backend.api.__init__`
- Purpose: (docstring not found)
- Public symbols: (none detected)
- Internal dependencies (0): (none)
- Used by (0): (none detected)

### `backend/api/error_handlers.py`
- Module: `backend.api.error_handlers`
- Purpose: FastAPI global exception handler ve standart hata cevabı.
- Public symbols: app_error_handler, http_exception_handler, register_exception_handlers, unhandled_exception_handler, validation_exception_handler
- Internal dependencies (2): backend.core.exceptions, backend.core.log_sanitizer
- Used by (12): backend/api/server.py, backend/tests/integration/test_api_auth_and_errors.py, backend/tests/test_account_deletion_api.py, backend/tests/test_clip_delete_routes.py, backend/tests/test_clip_transcript_routes.py, backend/tests/test_job_fairness.py, backend/tests/test_job_ownership.py, backend/tests/test_jobs_api_serialization.py, backend/tests/test_legacy_quarantine_migration.py, backend/tests/test_route_ownership_isolation.py, backend/tests/test_social_routes.py, backend/tests/test_support_grants.py

### `backend/api/routes/__init__.py`
- Module: `backend.api.routes.__init__`
- Purpose: (docstring not found)
- Public symbols: (none detected)
- Internal dependencies (0): (none)
- Used by (14): backend/api/server.py, backend/tests/test_account_deletion_api.py, backend/tests/test_clip_delete_routes.py, backend/tests/test_clip_transcript_recovery.py, backend/tests/test_clip_transcript_routes.py, backend/tests/test_clips_cache.py, backend/tests/test_job_fairness.py, backend/tests/test_job_ownership.py, backend/tests/test_jobs_api_serialization.py, backend/tests/test_jobs_cache_invalidation.py, backend/tests/test_legacy_quarantine_migration.py, backend/tests/test_route_ownership_isolation.py, backend/tests/test_social_routes.py, backend/tests/test_support_grants.py

### `backend/api/routes/account.py`
- Module: `backend.api.routes.account`
- Purpose: (docstring not found)
- Public symbols: delete_my_account_data
- Internal dependencies (4): backend.api.security, backend.core.exceptions, backend.models.schemas, backend.services.account_purge
- Used by (0): (none detected)

### `backend/api/routes/clips.py`
- Module: `backend.api.routes.clips`
- Purpose: backend/api/routes/clips.py
- Public symbols: ACTIVE_JOB_STATUSES, ALLOWED_CONTAINERS, ALLOWED_PROJECT_FILE_EXTENSIONS, ALLOWED_PROJECT_FILE_KINDS, CLIPS_CACHE_TTL_SECONDS, CLIP_RECOVERY_JOB_PREFIX, ClipsCacheState, FAILED_JOB_STATUSES, PROJECT_TRANSCRIPT_JOB_PREFIXES, SupportGrantRequest, build_clip_transcript_capabilities, build_clip_transcript_response, build_project_file_url, build_secure_clip_url, create_project_support_grant, delete_project_short, delete_project_support_grant, ensure_project_audio, ensure_project_transcript, extract_ui_title, finalize_job_error, finalize_job_success, find_clip_recovery_job, find_project_transcript_job, get_clip_transcript
- Internal dependencies (7): backend.api.security, backend.api.upload_validation, backend.api.websocket, backend.config, backend.core.exceptions, backend.services.ownership, backend.services.transcription
- Used by (4): backend/api/routes/editor.py, backend/api/routes/jobs.py, backend/tests/test_route_imports_smoke.py, backend/tests/unit/test_upload_prepare_project.py

### `backend/api/routes/editor.py`
- Module: `backend.api.routes.editor`
- Purpose: backend/api/routes/editor.py
- Public symbols: CLIP_RECOVERY_JOB_PREFIX, DEFAULT_MANUAL_CUT_LAYOUT, DEFAULT_MANUAL_CUT_STYLE, get_transcript, manual_cut_upload, process_batch_clips, process_manual_clip, reburn_clip, recover_clip_transcript, recover_project_transcript, save_transcript
- Internal dependencies (11): backend.api.routes.clips, backend.api.security, backend.api.websocket, backend.config, backend.core.exceptions, backend.core.media_ops, backend.core.orchestrator, backend.core.render_contracts, backend.models.schemas, backend.services.subtitle_styles, backend.services.transcription
- Used by (1): backend/tests/test_route_imports_smoke.py

### `backend/api/routes/jobs.py`
- Module: `backend.api.routes.jobs`
- Purpose: backend/api/routes/jobs.py
- Public symbols: cancel_job, get_available_styles, list_jobs, run_gpu_job, start_processing_job
- Internal dependencies (8): backend.api.routes.clips, backend.api.security, backend.api.websocket, backend.core.exceptions, backend.core.orchestrator, backend.core.render_contracts, backend.models.schemas, backend.services.subtitle_styles
- Used by (1): backend/tests/test_route_imports_smoke.py

### `backend/api/routes/social.py`
- Module: `backend.api.routes.social`
- Purpose: Social publishing endpoints (Postiz integration + scheduling).
- Public symbols: JobActionResponse, SocialCredentialRequest, SocialDraftRequest, SocialPublishDryRunRequest, SocialPublishRequest, SocialPublishTarget, approve_publish_job, cancel_publish_job, create_publish_jobs, delete_social_credentials, delete_social_drafts, dry_run_publish, export_social_media, get_social_prefill, list_connected_accounts, list_publish_jobs, save_social_credentials, save_social_drafts
- Internal dependencies (8): backend.api.security, backend.config, backend.core.exceptions, backend.services.social.constants, backend.services.social.crypto, backend.services.social.scheduler, backend.services.social.service, backend.services.social.store
- Used by (1): backend/tests/test_route_imports_smoke.py

### `backend/api/schemas.py`
- Module: `backend.api.schemas`
- Purpose: (docstring not found)
- Public symbols: ErrorResponse
- Internal dependencies (0): (none)
- Used by (0): (none detected)

### `backend/api/security.py`
- Module: `backend.api.security`
- Purpose: backend/api/security.py
- Public symbols: AuthContext, ClerkProviderUnavailableError, ClerkTokenExpiredError, WEAK_STATIC_TOKENS, authenticate_request, authenticate_websocket_token, ensure_project_access, ensure_project_owner, require_policy, validate_auth_configuration
- Internal dependencies (2): backend.core.log_sanitizer, backend.services.ownership
- Used by (12): backend/api/routes/account.py, backend/api/routes/clips.py, backend/api/routes/editor.py, backend/api/routes/jobs.py, backend/api/routes/social.py, backend/api/server.py, backend/tests/integration/test_api_auth_and_errors.py, backend/tests/test_api_security.py, backend/tests/test_clip_transcript_recovery.py, backend/tests/test_clips_cache.py, backend/tests/test_jobs_api_serialization.py, backend/tests/test_websocket_auth.py

### `backend/api/server.py`
- Module: `backend.api.server`
- Purpose: backend/api/server.py
- Public symbols: create_app, lifespan
- Internal dependencies (9): backend.api.error_handlers, backend.api.routes, backend.api.security, backend.api.websocket, backend.config, backend.runtime_validation, backend.services.social.crypto, backend.services.social.scheduler, backend.system_validation
- Used by (4): backend/main.py, backend/tests/test_route_imports_smoke.py, backend/tests/test_runtime_validation.py, backend/tests/test_social_crypto.py

### `backend/api/upload_validation.py`
- Module: `backend.api.upload_validation`
- Purpose: (docstring not found)
- Public symbols: ALLOWED_UPLOAD_EXTENSIONS, ALLOWED_UPLOAD_MIME_TYPES, DEFAULT_UPLOAD_CHUNK_SIZE, stream_upload_to_path, validate_upload, validate_upload_size
- Internal dependencies (2): backend.config, backend.core.exceptions
- Used by (2): backend/api/routes/clips.py, backend/tests/unit/test_upload_validation.py

### `backend/api/websocket.py`
- Module: `backend.api.websocket`
- Purpose: backend/api/websocket.py
- Public symbols: ConnectionManager, _MAX_PENDING_PER_JOB, get_main_loop, set_main_loop, thread_safe_broadcast
- Internal dependencies (1): backend.core.exceptions
- Used by (12): backend/api/routes/clips.py, backend/api/routes/editor.py, backend/api/routes/jobs.py, backend/api/server.py, backend/services/account_purge.py, backend/tests/test_job_fairness.py, backend/tests/test_job_ownership.py, backend/tests/test_jobs_api_serialization.py, backend/tests/test_jobs_cache_invalidation.py, backend/tests/test_subject_purge.py, backend/tests/test_websocket_subject_isolation.py, backend/tests/unit/test_job_lifecycle.py

### `backend/config.py`
- Module: `backend.config`
- Purpose: backend/config.py
- Public symbols: API_HOST, API_PORT, BACKEND_DIR, CORS_ORIGINS, DOWNLOADS_DIR, LOGS_DIR, MASTER_AUDIO, MASTER_VIDEO, MAX_UPLOAD_BYTES, METADATA_DIR, MODELS_DIR, OUTPUTS_DIR, PROJECTS_DIR, ProjectPaths, REQUEST_BODY_HARD_LIMIT_BYTES, ROOT, SUBJECT_HASH_PATTERN, TEMP_DIR, UPLOAD_MAX_FILE_SIZE, VIDEO_METADATA, VIRAL_SEGMENTS, WORKSPACE, YOLO_MODEL_PATH, ensure_workspace, extract_subject_hash_from_project_id
- Internal dependencies (0): (none)
- Used by (42): backend/api/routes/clips.py, backend/api/routes/editor.py, backend/api/routes/social.py, backend/api/server.py, backend/api/upload_validation.py, backend/core/media_ops.py, backend/core/orchestrator.py, backend/core/render_benchmark.py, backend/core/workflow_context.py, backend/core/workflow_helpers.py, backend/core/workflow_runtime.py, backend/core/workflows_manual.py, backend/core/workflows_reburn.py, backend/main.py, backend/services/account_purge.py, backend/services/ownership.py, backend/services/social/content.py, backend/services/social/service.py, backend/services/social/store.py, backend/services/subtitle_renderer.py

### `backend/core/__init__.py`
- Module: `backend.core.__init__`
- Purpose: (docstring not found)
- Public symbols: (none detected)
- Internal dependencies (1): backend.core.exceptions
- Used by (3): backend/tests/test_orchestrator_facade_dispatch.py, backend/tests/test_render_benchmark.py, backend/tests/test_workflow_runtime.py

### `backend/core/command_runner.py`
- Module: `backend.core.command_runner`
- Purpose: Subprocess execution with cancellation and timeout handling.
- Public symbols: CommandRunner, CompletedCommand
- Internal dependencies (0): (none)
- Used by (2): backend/core/media_ops.py, backend/core/orchestrator.py

### `backend/core/exception_handlers.py`
- Module: `backend.core.exception_handlers`
- Purpose: FastAPI global exception handler ve standart hata cevabı.
- Public symbols: app_error_handler, register_exception_handlers, unhandled_exception_handler, validation_exception_handler
- Internal dependencies (2): backend.core.exceptions, backend.core.log_sanitizer
- Used by (0): (none detected)

### `backend/core/exceptions.py`
- Module: `backend.core.exceptions`
- Purpose: Uygulama genelinde kullanılan domain-spesifik exception sınıfları.
- Public symbols: AppError, FileOperationError, InvalidInputError, JobExecutionError, MediaSubprocessError, NotFoundError, RateLimitError, TranscriptionError
- Internal dependencies (0): (none)
- Used by (12): backend/api/error_handlers.py, backend/api/routes/account.py, backend/api/routes/clips.py, backend/api/routes/editor.py, backend/api/routes/jobs.py, backend/api/routes/social.py, backend/api/upload_validation.py, backend/api/websocket.py, backend/core/__init__.py, backend/core/exception_handlers.py, backend/services/transcription.py, backend/tests/unit/test_upload_validation.py

### `backend/core/log_sanitizer.py`
- Module: `backend.core.log_sanitizer`
- Purpose: Helpers to keep sensitive values out of logs and generic error payloads.
- Public symbols: _PATH_PATTERNS, sanitize_log_value, sanitize_subject
- Internal dependencies (0): (none)
- Used by (4): backend/api/error_handlers.py, backend/api/security.py, backend/core/exception_handlers.py, backend/tests/test_log_sanitizer.py

### `backend/core/media_ops.py`
- Module: `backend.core.media_ops`
- Purpose: Media-level helper operations used by orchestration workflows.
- Public symbols: analyze_transcript_segments, build_shifted_transcript_segments, build_shifted_transcript_segments_with_report, cut_and_burn_clip, download_full_video_async, shift_timestamps, shift_timestamps_with_report
- Internal dependencies (5): backend.config, backend.core.command_runner, backend.core.subtitle_timing, backend.services.subtitle_renderer, backend.services.video_processor
- Used by (8): backend/api/routes/editor.py, backend/core/orchestrator.py, backend/core/render_benchmark.py, backend/core/workflow_helpers.py, backend/core/workflows_batch.py, backend/core/workflows_manual.py, backend/core/workflows_reburn.py, backend/tests/test_media_ops.py

### `backend/core/orchestrator.py`
- Module: `backend.core.orchestrator`
- Purpose: External facade orchestrator for GodTier Shorts workflows.
- Public symbols: GodTierShortsCreator
- Internal dependencies (8): backend.config, backend.core.command_runner, backend.core.media_ops, backend.core.workflows, backend.services.subtitle_renderer, backend.services.transcription, backend.services.video_processor, backend.services.viral_analyzer
- Used by (4): backend/api/routes/editor.py, backend/api/routes/jobs.py, backend/tests/test_orchestrator_shift.py, backend/tests/test_raw_video_saved.py

### `backend/core/render_benchmark.py`
- Module: `backend.core.render_benchmark`
- Purpose: Determinism and performance benchmarking helpers for clip renders.
- Public symbols: DEFAULT_BENCHMARK_RUNS, DEFAULT_BENCHMARK_SAMPLES, compare_benchmark_runs, compute_video_frame_hashes, normalize_render_metadata_for_comparison, read_peak_rss_mb, render_existing_clip_to_temp_output, render_existing_debug_environment, run_benchmark, select_sample_times
- Internal dependencies (7): backend.config, backend.core.media_ops, backend.core.render_quality, backend.core.workflow_helpers, backend.core.workflow_runtime, backend.services.subtitle_styles, backend.services.video_processor
- Used by (0): (none detected)

### `backend/core/render_contracts.py`
- Module: `backend.core.render_contracts`
- Purpose: Shared request/render contract helpers for layout and duration handling.
- Public symbols: ensure_valid_render_layout, ensure_valid_requested_layout, resolve_duration_range, resolve_duration_validation_status
- Internal dependencies (0): (none)
- Used by (9): backend/api/routes/editor.py, backend/api/routes/jobs.py, backend/core/workflow_helpers.py, backend/core/workflow_runtime.py, backend/models/schemas.py, backend/services/subtitle_styles.py, backend/services/video_processor.py, backend/services/viral_analyzer_core.py, backend/tests/test_render_contracts.py

### `backend/core/render_quality.py`
- Module: `backend.core.render_quality`
- Purpose: Render quality scoring, media probes, and environment fingerprint helpers.
- Public symbols: build_debug_environment, compute_render_quality_score, extract_media_stream_metrics, merge_transcript_quality, probe_media
- Internal dependencies (0): (none)
- Used by (7): backend/core/render_benchmark.py, backend/core/workflow_helpers.py, backend/core/workflows_manual.py, backend/core/workflows_reburn.py, backend/services/subtitle_renderer.py, backend/services/video_processor.py, backend/tests/test_render_quality.py

### `backend/core/subtitle_timing.py`
- Module: `backend.core.subtitle_timing`
- Purpose: Shared subtitle timing, normalization, chunking, and snapping helpers.
- Public symbols: DEFAULT_MAX_CHUNK_DURATION, DEFAULT_MAX_MERGED_CHUNK_DURATION, DEFAULT_MAX_WORDS_PER_SCREEN, DEFAULT_MIN_CHUNK_DURATION, DEFAULT_WORD_GAP_BREAK, STRONG_PUNCTUATION, WEAK_PUNCTUATION, WHITESPACE_PATTERN, ZERO_WIDTH_PATTERN, average_chunk_words, build_chunk_payload, chunk_ends_with_strong_punctuation, chunk_words, clamp01, collect_valid_words, compute_word_coverage_ratio, count_normalized_tokens, get_chunk_duration, get_chunk_text, has_strong_punctuation, has_weak_punctuation, iter_word_boundaries, normalize_subtitle_text, normalize_word_payload, resolve_snap_window
- Internal dependencies (0): (none)
- Used by (4): backend/core/media_ops.py, backend/core/workflow_helpers.py, backend/services/subtitle_renderer.py, backend/tests/test_subtitle_timing.py

### `backend/core/workflow_context.py`
- Module: `backend.core.workflow_context`
- Purpose: Shared protocol contracts for workflow modules.
- Public symbols: OrchestratorContext
- Internal dependencies (3): backend.config, backend.services.subtitle_renderer, backend.services.video_processor
- Used by (5): backend/core/workflows.py, backend/core/workflows_batch.py, backend/core/workflows_manual.py, backend/core/workflows_pipeline.py, backend/core/workflows_reburn.py

### `backend/core/workflow_helpers.py`
- Module: `backend.core.workflow_helpers`
- Purpose: Shared helpers for orchestrator workflow modules.
- Public symbols: ProgressStepMapper, TempArtifactManager, analyze_pipeline_segments, apply_opening_validation, build_hook_slug, ensure_pipeline_master_assets, ensure_pipeline_transcript, load_json_dict, move_file_atomic, persist_debug_artifacts, prepare_pipeline_project, render_batch_segments, render_pipeline_segments, run_blocking, run_cut_points_workflow, write_json_atomic, write_reburn_metadata
- Internal dependencies (11): backend.config, backend.core.media_ops, backend.core.render_contracts, backend.core.render_quality, backend.core.subtitle_timing, backend.core.workflow_runtime, backend.core.workflows_manual, backend.services.ownership, backend.services.subtitle_renderer, backend.services.subtitle_styles, backend.services.transcription
- Used by (6): backend/core/render_benchmark.py, backend/core/workflows_batch.py, backend/core/workflows_manual.py, backend/core/workflows_pipeline.py, backend/core/workflows_reburn.py, backend/tests/test_workflow_helpers.py

### `backend/core/workflow_runtime.py`
- Module: `backend.core.workflow_runtime`
- Purpose: Shared runtime helpers for workflow modules.
- Public symbols: LOWER_THIRD_PROBE_SAMPLE_COUNT, LOWER_THIRD_PROBE_WINDOW_SECONDS, LOWER_THIRD_SAFE_AREA_PROFILE, SubtitleRenderPlan, create_subtitle_renderer, probe_video_canvas, resolve_output_video_path, resolve_project_master_video, resolve_subtitle_render_plan
- Internal dependencies (6): backend.config, backend.core.render_contracts, backend.services.ownership, backend.services.subtitle_renderer, backend.services.subtitle_styles, backend.services.video_processor
- Used by (5): backend/core/render_benchmark.py, backend/core/workflow_helpers.py, backend/core/workflows_batch.py, backend/core/workflows_manual.py, backend/core/workflows_reburn.py

### `backend/core/workflows.py`
- Module: `backend.core.workflows`
- Purpose: Public workflow exports.
- Public symbols: (none detected)
- Internal dependencies (5): backend.core.workflow_context, backend.core.workflows_batch, backend.core.workflows_manual, backend.core.workflows_pipeline, backend.core.workflows_reburn
- Used by (2): backend/core/orchestrator.py, backend/tests/test_workflows_refactor_guardrails.py

### `backend/core/workflows_batch.py`
- Module: `backend.core.workflows_batch`
- Purpose: Batch clip workflow implementation.
- Public symbols: BatchClipWorkflow, resolve_project_master_video
- Internal dependencies (4): backend.core.media_ops, backend.core.workflow_context, backend.core.workflow_helpers, backend.core.workflow_runtime
- Used by (2): backend/core/workflows.py, backend/tests/test_workflows_batch.py

### `backend/core/workflows_manual.py`
- Module: `backend.core.workflows_manual`
- Purpose: Manual clip workflows (single + cut-points).
- Public symbols: CutPointsWorkflow, ManualClipWorkflow
- Internal dependencies (8): backend.config, backend.core.media_ops, backend.core.render_quality, backend.core.workflow_context, backend.core.workflow_helpers, backend.core.workflow_runtime, backend.services.subtitle_renderer, backend.services.subtitle_styles
- Used by (2): backend/core/workflow_helpers.py, backend/core/workflows.py

### `backend/core/workflows_pipeline.py`
- Module: `backend.core.workflows_pipeline`
- Purpose: Pipeline workflow implementation.
- Public symbols: PipelineWorkflow, release_whisper_models, run_transcription
- Internal dependencies (3): backend.core.workflow_context, backend.core.workflow_helpers, backend.services.transcription
- Used by (2): backend/core/workflows.py, backend/tests/test_workflows_pipeline.py

### `backend/core/workflows_reburn.py`
- Module: `backend.core.workflows_reburn`
- Purpose: Subtitle reburn workflow implementation.
- Public symbols: ReburnWorkflow
- Internal dependencies (7): backend.config, backend.core.media_ops, backend.core.render_quality, backend.core.workflow_context, backend.core.workflow_helpers, backend.core.workflow_runtime, backend.services.subtitle_styles
- Used by (1): backend/core/workflows.py

### `backend/main.py`
- Module: `backend.main`
- Purpose: backend/main.py
- Public symbols: (none detected)
- Internal dependencies (2): backend.api.server, backend.config
- Used by (0): (none detected)

### `backend/models/__init__.py`
- Module: `backend.models.__init__`
- Purpose: Pydantic schema models for backend request/response payloads.
- Public symbols: (none detected)
- Internal dependencies (0): (none)
- Used by (0): (none detected)

### `backend/models/schemas.py`
- Module: `backend.models.schemas`
- Purpose: Request payload schemas used by job/editor routes.
- Public symbols: AccountDeletionRequest, BatchJobRequest, ClipTranscriptRecoveryRequest, JobRequest, ManualAutoCutRequest, ManualJobRequest, ProjectTranscriptRecoveryRequest, ReburnRequest, TranscriptSegment
- Internal dependencies (2): backend.core.render_contracts, backend.services.subtitle_styles
- Used by (7): backend/api/routes/account.py, backend/api/routes/editor.py, backend/api/routes/jobs.py, backend/tests/smoke/test_smoke_job_request.py, backend/tests/test_clip_transcript_recovery.py, backend/tests/test_job_request.py, backend/tests/test_jobs_cache_invalidation.py

### `backend/runtime_validation.py`
- Module: `backend.runtime_validation`
- Purpose: Runtime configuration validation helpers.
- Public symbols: validate_runtime_configuration
- Internal dependencies (0): (none)
- Used by (2): backend/api/server.py, backend/tests/test_runtime_validation.py

### `backend/services/__init__.py`
- Module: `backend.services.__init__`
- Purpose: (docstring not found)
- Public symbols: (none detected)
- Internal dependencies (0): (none)
- Used by (1): backend/tests/test_project_ownership.py

### `backend/services/account_purge.py`
- Module: `backend.services.account_purge`
- Purpose: Delete subject-owned runtime data while preserving security/audit logs.
- Public symbols: purge_subject_data
- Internal dependencies (4): backend.api.websocket, backend.config, backend.services.ownership, backend.services.social.store
- Used by (2): backend/api/routes/account.py, backend/tests/test_subject_purge.py

### `backend/services/ownership.py`
- Module: `backend.services.ownership`
- Purpose: Ownership manifests and per-subject project access helpers.
- Public symbols: DEFAULT_SUPPORT_GRANT_TTL_SECONDS, PROJECT_MANIFEST_FILENAME, PROJECT_MANIFEST_SCHEMA_VERSION, ProjectOwnershipManifest, SupportGrant, build_owner_scoped_project_id, build_subject_hash, create_project_manifest, ensure_project_manifest, grant_support_access, is_support_subject_allowed, list_accessible_project_ids, project_manifest_path, quarantine_legacy_projects, quarantine_project, read_project_manifest, resolve_project_access, revoke_support_access, scrub_support_grants_for_subject, write_project_manifest
- Internal dependencies (1): backend.config
- Used by (20): backend/api/routes/clips.py, backend/api/security.py, backend/core/workflow_helpers.py, backend/core/workflow_runtime.py, backend/services/account_purge.py, backend/services/social/service.py, backend/tests/test_account_deletion_api.py, backend/tests/test_clip_delete_routes.py, backend/tests/test_clip_transcript_recovery.py, backend/tests/test_clip_transcript_routes.py, backend/tests/test_clips_cache.py, backend/tests/test_legacy_quarantine_migration.py, backend/tests/test_route_ownership_isolation.py, backend/tests/test_social_content.py, backend/tests/test_social_routes.py, backend/tests/test_subject_purge.py, backend/tests/test_support_grants.py, backend/tests/test_workflow_helpers.py, backend/tests/test_workflow_runtime.py, backend/tests/unit/test_upload_prepare_project.py

### `backend/services/social/__init__.py`
- Module: `backend.services.social.__init__`
- Purpose: Social publishing services package.
- Public symbols: (none detected)
- Internal dependencies (0): (none)
- Used by (0): (none detected)

### `backend/services/social/constants.py`
- Module: `backend.services.social.constants`
- Purpose: Constants and platform mappings for social publishing.
- Public symbols: SOCIAL_PROVIDER_POSTIZ
- Internal dependencies (0): (none)
- Used by (1): backend/api/routes/social.py

### `backend/services/social/content.py`
- Module: `backend.services.social.content`
- Purpose: Prefill generation and viral metadata fallback helpers.
- Public symbols: _HASHTAG_RE, build_platform_prefill, extract_hashtags, resolve_clip_metadata_paths, resolve_viral_metadata, strip_hashtags
- Internal dependencies (1): backend.config
- Used by (1): backend/tests/test_social_content.py

### `backend/services/social/crypto.py`
- Module: `backend.services.social.crypto`
- Purpose: Simple encryption wrapper for user-level social credentials.
- Public symbols: SocialCrypto, get_social_encryption_secret, validate_social_security_configuration
- Internal dependencies (0): (none)
- Used by (3): backend/api/routes/social.py, backend/api/server.py, backend/tests/test_social_crypto.py

### `backend/services/social/postiz.py`
- Module: `backend.services.social.postiz`
- Purpose: Postiz Public API client helpers.
- Public symbols: PostizApiError, PostizClient
- Internal dependencies (0): (none)
- Used by (1): backend/tests/test_social_postiz.py

### `backend/services/social/scheduler.py`
- Module: `backend.services.social.scheduler`
- Purpose: Background scheduler that executes due social publish jobs.
- Public symbols: SocialPublishScheduler, get_social_scheduler
- Internal dependencies (0): (none)
- Used by (2): backend/api/routes/social.py, backend/api/server.py

### `backend/services/social/service.py`
- Module: `backend.services.social.service`
- Purpose: High-level social publishing orchestration helpers.
- Public symbols: RETRY_BACKOFF_MINUTES, build_clip_prefill, build_signed_social_export_token, build_signed_social_export_url, compute_retry_eta, create_scheduled_post_now, delete_scheduled_post_from_postiz, dry_run_publish_via_postiz, get_postiz_api_key_from_env, get_postiz_client_for_subject, has_postiz_credential_configured, normalize_postiz_accounts, publish_job_via_postiz, resolve_signed_social_export_token, run_publish_attempt, validate_postiz_credential
- Internal dependencies (2): backend.config, backend.services.ownership
- Used by (3): backend/api/routes/social.py, backend/tests/test_social_postiz.py, backend/tests/test_social_routes.py

### `backend/services/social/store.py`
- Module: `backend.services.social.store`
- Purpose: SQLite-backed persistence for social credentials, drafts, and publish jobs.
- Public symbols: DB_PATH, SocialStore, get_social_store, parse_iso, utcnow_iso
- Internal dependencies (1): backend.config
- Used by (5): backend/api/routes/social.py, backend/services/account_purge.py, backend/tests/test_account_deletion_api.py, backend/tests/test_social_routes.py, backend/tests/test_subject_purge.py

### `backend/services/subtitle_renderer.py`
- Module: `backend.services.subtitle_renderer`
- Purpose: backend/services/subtitle_renderer.py
- Public symbols: NARROW_CHARACTERS, PUNCTUATION_CHARACTERS, SINGLE_MIN_FONT_SCALE, SMALL_GAP_BRIDGE_THRESHOLD, SPLIT_FONT_CLAMP_MARGIN, SPLIT_HARD_OVERFLOW_RATIO, SPLIT_MAX_WORDS_PER_SCREEN, SPLIT_MIN_FONT_SCALE, SPLIT_SOFT_WRAP_RATIO, SubtitleRenderer, WIDE_LOWER_CHARACTERS
- Internal dependencies (4): backend.config, backend.core.render_quality, backend.core.subtitle_timing, backend.services.subtitle_styles
- Used by (7): backend/core/media_ops.py, backend/core/orchestrator.py, backend/core/workflow_context.py, backend/core/workflow_helpers.py, backend/core/workflow_runtime.py, backend/core/workflows_manual.py, backend/tests/test_subtitle_renderer.py

### `backend/services/subtitle_styles.py`
- Module: `backend.services.subtitle_styles`
- Purpose: backend/services/subtitle_styles.py
- Public symbols: EXPLICIT_ANIMATION_TYPES, GLOW_STYLE_KEYS, LOGICAL_CANVAS_HEIGHT, LOGICAL_CANVAS_WIDTH, ResolvedSubtitleRenderSpec, SINGLE_LINE_HEIGHT, SPLIT_FONT_SCALE, SPLIT_GUTTER_HEIGHT, SPLIT_LINE_HEIGHT, SPLIT_PANEL_HEIGHT, StyleManager, SubtitleAnimationSpec, SubtitleCanvasSpec, SubtitleCategory, SubtitleMotionPreset, SubtitleSafeAreaSpec, SubtitleStyle, VALID_ANIMATION_TYPES, VALID_LAYOUTS, VALID_REQUEST_LAYOUTS_SET, VALID_SAFE_AREA_PROFILES
- Internal dependencies (1): backend.core.render_contracts
- Used by (12): backend/api/routes/editor.py, backend/api/routes/jobs.py, backend/core/render_benchmark.py, backend/core/workflow_helpers.py, backend/core/workflow_runtime.py, backend/core/workflows_manual.py, backend/core/workflows_reburn.py, backend/models/schemas.py, backend/services/subtitle_renderer.py, backend/services/video_processor.py, backend/tests/test_subtitle_renderer.py, backend/tests/test_subtitle_styles.py

### `backend/services/transcription.py`
- Module: `backend.services.transcription`
- Purpose: backend/services/transcription.py
- Public symbols: DEVICE, HF_TOKEN, LOCAL_MODEL_REQUIRED_FILES, release_whisper_models, run_transcription
- Internal dependencies (2): backend.config, backend.core.exceptions
- Used by (5): backend/api/routes/clips.py, backend/api/routes/editor.py, backend/core/orchestrator.py, backend/core/workflow_helpers.py, backend/core/workflows_pipeline.py

### `backend/services/video_processor.py`
- Module: `backend.services.video_processor`
- Purpose: backend/services/video_processor.py
- Public symbols: CONTROLLED_RETURN_FRAMES, CPU_TRACKING_STRIDE, DETECTION_LONG_EDGE, DIFF_ID_REACQUIRE_CENTER_RATIO, DetectionCandidate, HARD_CUT_THRESHOLD, MIN_DETECTION_CONFIDENCE, MIN_TRACK_ACCEPT_SCORE, MISSING_TRACK_GRACE_FRAMES, OPENING_MAX_SHIFT_SECONDS, OPENING_SAMPLE_COUNT, OPENING_VISIBILITY_OK_SECONDS, OPENING_VISIBILITY_WINDOW_SECONDS, REACQUIRE_CONFIRMATION_FRAMES, SAME_ID_REACQUIRE_CENTER_RATIO, SINGLE_DEADZONE_RATIO, SINGLE_EMA_ALPHA, SINGLE_MAX_STEP_RATIO, SOFT_CUT_THRESHOLD, SPLIT_CONTROLLED_RETURN_PAN_RATIO, SPLIT_DEADZONE_RATIO, SPLIT_EMA_ALPHA, SPLIT_FALLBACK_DEADZONE_RATIO, SPLIT_FALLBACK_SUSTAINED_FRAMES, SPLIT_JITTER_DEGRADED_THRESHOLD_PX
- Internal dependencies (4): backend.config, backend.core.render_contracts, backend.core.render_quality, backend.services.subtitle_styles
- Used by (8): backend/core/media_ops.py, backend/core/orchestrator.py, backend/core/render_benchmark.py, backend/core/workflow_context.py, backend/core/workflow_runtime.py, backend/tests/test_manual_crop.py, backend/tests/test_video_processor_crop_bounds.py, backend/tests/test_video_processor_layout.py

### `backend/services/viral_analyzer.py`
- Module: `backend.services.viral_analyzer`
- Purpose: (docstring not found)
- Public symbols: ViralAnalysisResult, ViralAnalyzer, ViralSegment
- Internal dependencies (3): backend.config, backend.services.viral_analyzer_core, backend.services.viral_llm_adapters
- Used by (2): backend/core/orchestrator.py, backend/tests/test_viral_analyzer_params.py

### `backend/services/viral_analyzer_core.py`
- Module: `backend.services.viral_analyzer_core`
- Purpose: Pure helpers for ViralAnalyzer prompting/parsing/fallback logic.
- Public symbols: build_fallback_segments, build_metadata_prompt, build_segment_prompt, build_transcript_text, clip_words, default_segments_schema_json, extract_message_content, normalize_hook, normalize_viral_segments, parse_llm_json_response
- Internal dependencies (1): backend.core.render_contracts
- Used by (2): backend/services/viral_analyzer.py, backend/tests/test_viral_analyzer_params.py

### `backend/services/viral_llm_adapters.py`
- Module: `backend.services.viral_llm_adapters`
- Purpose: Provider adapters for ViralAnalyzer LLM calls.
- Public symbols: LMStudioAdapter, OpenRouterAdapter, SYSTEM_PROMPT, ViralLLMAdapter, create_adapter, engine_label
- Internal dependencies (0): (none)
- Used by (1): backend/services/viral_analyzer.py

### `backend/system_validation.py`
- Module: `backend.system_validation`
- Purpose: System dependency validation helpers for fresh installs.
- Public symbols: NVENC_SMOKE_DIMENSIONS, SystemCheckResult, log_system_dependency_results, run_system_dependency_checks, summarize_failures, validate_accelerator_support_configuration
- Internal dependencies (0): (none)
- Used by (2): backend/api/server.py, backend/tests/test_system_validation.py

### `backend/tests/__init__.py`
- Module: `backend.tests.__init__`
- Purpose: (docstring not found)
- Public symbols: (none detected)
- Internal dependencies (0): (none)
- Used by (0): (none detected)

### `backend/tests/compat_testclient.py`
- Module: `backend.tests.compat_testclient`
- Purpose: (docstring not found)
- Public symbols: CompatTestClient
- Internal dependencies (0): (none)
- Used by (1): backend/tests/conftest.py

### `backend/tests/conftest.py`
- Module: `backend.tests.conftest`
- Purpose: backend/tests/conftest.py
- Public symbols: sample_transcript
- Internal dependencies (1): backend.tests.compat_testclient
- Used by (0): (none detected)

### `backend/tests/integration/test_api_auth_and_errors.py`
- Module: `backend.tests.integration.test_api_auth_and_errors`
- Purpose: (docstring not found)
- Public symbols: build_app, test_auth_required_returns_standard_error, test_standard_error_response_schema
- Internal dependencies (2): backend.api.error_handlers, backend.api.security
- Used by (0): (none detected)

### `backend/tests/smoke/test_smoke_job_request.py`
- Module: `backend.tests.smoke.test_smoke_job_request`
- Purpose: (docstring not found)
- Public symbols: test_smoke_job_request_minimal
- Internal dependencies (1): backend.models.schemas
- Used by (0): (none detected)

### `backend/tests/test_account_deletion_api.py`
- Module: `backend.tests.test_account_deletion_api`
- Purpose: (docstring not found)
- Public symbols: auth_headers, social_store, test_account_deletion_purges_only_callers_subject_data_and_logs_event, test_account_deletion_requires_typed_confirmation
- Internal dependencies (5): backend.api.error_handlers, backend.api.routes, backend.config, backend.services.ownership, backend.services.social.store
- Used by (0): (none detected)

### `backend/tests/test_api_security.py`
- Module: `backend.tests.test_api_security`
- Purpose: Auth ve policy helper testleri.
- Public symbols: test_authenticate_websocket_token_with_static_token, test_authenticate_with_static_token, test_expired_clerk_token_returns_specific_code, test_missing_bearer_returns_401_json, test_policy_rejects_insufficient_role, test_read_policy_requires_auth, test_unreachable_clerk_provider_returns_503, test_validate_auth_configuration_requires_audience
- Internal dependencies (1): backend.api.security
- Used by (0): (none detected)

### `backend/tests/test_clip_delete_routes.py`
- Module: `backend.tests.test_clip_delete_routes`
- Purpose: (docstring not found)
- Public symbols: auth_headers, test_delete_project_short_handles_missing_optional_assets, test_delete_project_short_removes_managed_assets_and_preserves_project_files, test_delete_project_short_requires_delete_policy, test_delete_project_short_returns_not_found_without_invalidation
- Internal dependencies (4): backend.api.error_handlers, backend.api.routes, backend.config, backend.services.ownership
- Used by (0): (none detected)

### `backend/tests/test_clip_transcript_recovery.py`
- Module: `backend.tests.test_clip_transcript_recovery`
- Purpose: (docstring not found)
- Public symbols: test_recover_clip_transcript_auto_falls_back_to_source_when_project_slice_is_empty, test_recover_clip_transcript_dedupes_active_jobs, test_recover_clip_transcript_from_project_slice, test_recover_clip_transcript_prefers_raw_video_source, test_recover_project_transcript_reuses_existing_job
- Internal dependencies (5): backend.api.routes, backend.api.security, backend.config, backend.models.schemas, backend.services.ownership
- Used by (0): (none detected)

### `backend/tests/test_clip_transcript_routes.py`
- Module: `backend.tests.test_clip_transcript_routes`
- Purpose: (docstring not found)
- Public symbols: auth_headers, test_get_clip_transcript_includes_recovery_capabilities, test_get_clip_transcript_reports_project_pending_status, test_get_clip_transcript_reports_source_transcription_only_when_metadata_is_missing, test_get_project_transcript_reports_pending_and_failed_states
- Internal dependencies (4): backend.api.error_handlers, backend.api.routes, backend.config, backend.services.ownership
- Used by (0): (none detected)

### `backend/tests/test_clips_cache.py`
- Module: `backend.tests.test_clips_cache`
- Purpose: (docstring not found)
- Public symbols: test_clips_cache_invalidation_after_success, test_clips_cache_ttl_refresh, test_clips_index_cache_reuses_scan, test_clips_index_excludes_legacy_flat_project_folders, test_clips_index_hides_internal_raw_and_reburn_assets, test_clips_page_cache_is_partitioned_by_subject, test_clips_pagination_contract_unchanged
- Internal dependencies (4): backend.api.routes, backend.api.security, backend.config, backend.services.ownership
- Used by (0): (none detected)

### `backend/tests/test_dependency_manifest.py`
- Module: `backend.tests.test_dependency_manifest`
- Purpose: Checks that runtime backend imports are represented in requirements.txt.
- Public symbols: REQUIREMENTS_PATH, test_requirements_cover_critical_runtime_dependencies
- Internal dependencies (0): (none)
- Used by (0): (none detected)

### `backend/tests/test_job_fairness.py`
- Module: `backend.tests.test_job_fairness`
- Purpose: (docstring not found)
- Public symbols: auth_headers, test_other_subject_can_enqueue_when_foreign_queue_is_full, test_start_job_rejects_when_subject_pending_limit_is_reached, test_subject_job_counts_distinguish_processing_and_queued
- Internal dependencies (3): backend.api.error_handlers, backend.api.routes, backend.api.websocket
- Used by (0): (none detected)

### `backend/tests/test_job_ownership.py`
- Module: `backend.tests.test_job_ownership`
- Purpose: (docstring not found)
- Public symbols: auth_headers, test_foreign_job_cancel_returns_not_found, test_jobs_endpoint_lists_only_callers_subject_jobs, test_owner_can_cancel_own_job
- Internal dependencies (3): backend.api.error_handlers, backend.api.routes, backend.api.websocket
- Used by (0): (none detected)

### `backend/tests/test_job_request.py`
- Module: `backend.tests.test_job_request`
- Purpose: backend/tests/test_job_request.py
- Public symbols: test_job_request_accepts_new_fields, test_job_request_auto_mode_false_rejects_invalid_range, test_job_request_auto_mode_false_requires_valid_duration, test_job_request_auto_mode_true_uses_defaults, test_job_request_duration_bounds, test_job_request_num_clips_range, test_job_request_rejects_unknown_style_name, test_job_request_validates_animation_type, test_job_request_validates_layout_name
- Internal dependencies (1): backend.models.schemas
- Used by (0): (none detected)

### `backend/tests/test_jobs_api_serialization.py`
- Module: `backend.tests.test_jobs_api_serialization`
- Purpose: (docstring not found)
- Public symbols: test_jobs_endpoint_omits_runtime_task_objects
- Internal dependencies (4): backend.api.error_handlers, backend.api.routes, backend.api.security, backend.api.websocket
- Used by (0): (none detected)

### `backend/tests/test_jobs_cache_invalidation.py`
- Module: `backend.tests.test_jobs_cache_invalidation`
- Purpose: (docstring not found)
- Public symbols: test_run_gpu_job_invalidates_clip_cache_after_success
- Internal dependencies (3): backend.api.routes, backend.api.websocket, backend.models.schemas
- Used by (0): (none detected)

### `backend/tests/test_legacy_quarantine_migration.py`
- Module: `backend.tests.test_legacy_quarantine_migration`
- Purpose: (docstring not found)
- Public symbols: auth_headers, test_quarantine_legacy_projects_script_marks_legacy_dirs_and_hides_them
- Internal dependencies (4): backend.api.error_handlers, backend.api.routes, backend.config, backend.services.ownership
- Used by (0): (none detected)

### `backend/tests/test_log_sanitizer.py`
- Module: `backend.tests.test_log_sanitizer`
- Purpose: (docstring not found)
- Public symbols: test_sanitize_log_value_recurses_into_nested_payloads, test_sanitize_log_value_redacts_workspace_paths, test_sanitize_subject_returns_stable_fingerprint
- Internal dependencies (1): backend.core.log_sanitizer
- Used by (0): (none detected)

### `backend/tests/test_manual_crop.py`
- Module: `backend.tests.test_manual_crop`
- Purpose: backend/tests/test_manual_crop.py
- Public symbols: test_manual_crop
- Internal dependencies (2): backend.config, backend.services.video_processor
- Used by (0): (none detected)

### `backend/tests/test_media_ops.py`
- Module: `backend.tests.test_media_ops`
- Purpose: (docstring not found)
- Public symbols: test_build_shifted_transcript_segments_preserves_overlapping_segments_without_words, test_build_shifted_transcript_segments_rebuilds_text_from_retained_words, test_build_shifted_transcript_segments_with_report_tracks_quality_fields, test_cut_and_burn_clip_moves_final_output_when_subtitles_are_skipped, test_cut_and_burn_clip_saves_raw_copy_before_burn
- Internal dependencies (1): backend.core.media_ops
- Used by (0): (none detected)

### `backend/tests/test_orchestrator_facade_dispatch.py`
- Module: `backend.tests.test_orchestrator_facade_dispatch`
- Purpose: (docstring not found)
- Public symbols: test_reburn_subtitles_async_dispatches_to_reburn_workflow, test_run_batch_manual_clips_async_dispatches_to_batch_workflow, test_run_manual_clip_async_dispatches_to_manual_workflow, test_run_manual_clips_from_cut_points_async_dispatches_to_cut_points_workflow, test_run_pipeline_async_dispatches_to_pipeline_workflow
- Internal dependencies (1): backend.core
- Used by (0): (none detected)

### `backend/tests/test_orchestrator_refactor_guardrails.py`
- Module: `backend.tests.test_orchestrator_refactor_guardrails`
- Purpose: Guardrail tests for orchestrator facade size and method length budgets.
- Public symbols: FACADE_METHODS, MAX_FACADE_METHOD_LINES, MAX_ORCHESTRATOR_LINES, ORCHESTRATOR_PATH, test_facade_method_line_budget, test_orchestrator_file_line_budget
- Internal dependencies (0): (none)
- Used by (0): (none detected)

### `backend/tests/test_orchestrator_shift.py`
- Module: `backend.tests.test_orchestrator_shift`
- Purpose: backend/tests/test_orchestrator_shift.py
- Public symbols: TestShiftTimestamps
- Internal dependencies (1): backend.core.orchestrator
- Used by (0): (none detected)

### `backend/tests/test_project_layout.py`
- Module: `backend.tests.test_project_layout`
- Purpose: (docstring not found)
- Public symbols: test_extract_subject_hash_from_owner_scoped_project_id, test_flat_project_ids_are_rejected, test_project_paths_use_nested_subject_layout
- Internal dependencies (1): backend.config
- Used by (0): (none detected)

### `backend/tests/test_project_ownership.py`
- Module: `backend.tests.test_project_ownership`
- Purpose: (docstring not found)
- Public symbols: test_build_subject_hash_is_stable_and_32_chars, test_expired_support_grant_is_denied, test_manifest_round_trip_and_owner_access, test_missing_manifest_is_denied_and_treated_as_quarantine, test_quarantined_manifest_is_not_accessible, test_support_grant_allows_temporary_cross_subject_access
- Internal dependencies (2): backend.config, backend.services
- Used by (0): (none detected)

### `backend/tests/test_raw_video_saved.py`
- Module: `backend.tests.test_raw_video_saved`
- Purpose: backend/tests/test_raw_video_saved.py
- Public symbols: test_run_manual_clip_saves_raw_video
- Internal dependencies (2): backend.config, backend.core.orchestrator
- Used by (0): (none detected)

### `backend/tests/test_render_benchmark.py`
- Module: `backend.tests.test_render_benchmark`
- Purpose: (docstring not found)
- Public symbols: test_benchmark_script_smoke, test_compare_benchmark_runs_detects_matching_payloads, test_run_benchmark_writes_report_and_cleans_outputs, test_select_sample_times_spreads_across_duration
- Internal dependencies (1): backend.core
- Used by (0): (none detected)

### `backend/tests/test_render_contracts.py`
- Module: `backend.tests.test_render_contracts`
- Purpose: (docstring not found)
- Public symbols: test_ensure_valid_requested_layout_accepts_auto, test_resolve_duration_range_swaps_reversed_values, test_resolve_duration_range_uses_shared_defaults, test_resolve_duration_validation_status_reports_bounds
- Internal dependencies (1): backend.core.render_contracts
- Used by (0): (none detected)

### `backend/tests/test_render_quality.py`
- Module: `backend.tests.test_render_quality`
- Purpose: (docstring not found)
- Public symbols: test_compute_render_quality_score_caps_fallback_tracking, test_merge_transcript_quality_marks_overflow_as_degraded
- Internal dependencies (1): backend.core.render_quality
- Used by (0): (none detected)

### `backend/tests/test_route_imports_smoke.py`
- Module: `backend.tests.test_route_imports_smoke`
- Purpose: Smoke tests for route modules that depend on backend.models.schemas.
- Public symbols: test_route_modules_import
- Internal dependencies (5): backend.api.routes.clips, backend.api.routes.editor, backend.api.routes.jobs, backend.api.routes.social, backend.api.server
- Used by (0): (none detected)

### `backend/tests/test_route_ownership_isolation.py`
- Module: `backend.tests.test_route_ownership_isolation`
- Purpose: (docstring not found)
- Public symbols: auth_headers, test_foreign_project_assets_and_transcript_return_not_found, test_foreign_project_denial_is_security_logged, test_projects_and_clips_are_filtered_by_owner
- Internal dependencies (4): backend.api.error_handlers, backend.api.routes, backend.config, backend.services.ownership
- Used by (0): (none detected)

### `backend/tests/test_runtime_validation.py`
- Module: `backend.tests.test_runtime_validation`
- Purpose: (docstring not found)
- Public symbols: test_create_app_startup_requires_accelerator_support_when_validation_fails, test_create_app_startup_requires_valid_runtime_configuration, test_validate_runtime_configuration_accepts_defaults, test_validate_runtime_configuration_rejects_invalid_cors_origin, test_validate_runtime_configuration_rejects_invalid_frontend_url, test_validate_runtime_configuration_rejects_invalid_gpu_flags, test_validate_runtime_configuration_rejects_invalid_port, test_validate_runtime_configuration_rejects_invalid_postiz_base_url, test_validate_runtime_configuration_rejects_invalid_scheduler_concurrency, test_validate_runtime_configuration_rejects_smaller_request_limit
- Internal dependencies (2): backend.api.server, backend.runtime_validation
- Used by (0): (none detected)

### `backend/tests/test_social_content.py`
- Module: `backend.tests.test_social_content`
- Purpose: (docstring not found)
- Public symbols: test_build_platform_prefill_applies_x_limit, test_extract_hashtags_deduplicates_and_normalizes, test_resolve_viral_metadata_falls_back_to_viral_json
- Internal dependencies (3): backend.config, backend.services.ownership, backend.services.social.content
- Used by (0): (none detected)

### `backend/tests/test_social_crypto.py`
- Module: `backend.tests.test_social_crypto`
- Purpose: Tests for social credential encryption hardening.
- Public symbols: test_create_app_startup_requires_social_secret, test_get_social_encryption_secret_prefers_explicit_value, test_social_crypto_requires_secret, test_social_crypto_round_trip, test_validate_social_security_configuration_requires_secret
- Internal dependencies (2): backend.api.server, backend.services.social.crypto
- Used by (0): (none detected)

### `backend/tests/test_social_postiz.py`
- Module: `backend.tests.test_social_postiz`
- Purpose: (docstring not found)
- Public symbols: test_postiz_client_falls_back_to_api_public_v1, test_postiz_create_post_normalizes_tags
- Internal dependencies (2): backend.services.social.postiz, backend.services.social.service
- Used by (0): (none detected)

### `backend/tests/test_social_routes.py`
- Module: `backend.tests.test_social_routes`
- Purpose: (docstring not found)
- Public symbols: auth_header, social_secret, social_store, test_approve_future_scheduled_job_creates_remote_schedule, test_cancel_scheduled_job_deletes_remote_post, test_due_jobs_exclude_legacy_scheduled_drafts, test_scheduled_publish_is_synced_to_postiz_immediately, test_social_accounts_uses_env_fallback, test_social_credentials_and_accounts_endpoint, test_social_export_rejects_invalid_or_expired_token_with_log, test_social_export_serves_clip_for_valid_signed_token, test_social_prefill_drafts_and_publish, test_social_publish_dry_run, test_social_routes_reject_foreign_project_access, test_social_user_isolation
- Internal dependencies (6): backend.api.error_handlers, backend.api.routes, backend.config, backend.services.ownership, backend.services.social.service, backend.services.social.store
- Used by (0): (none detected)

### `backend/tests/test_subject_purge.py`
- Module: `backend.tests.test_subject_purge`
- Purpose: (docstring not found)
- Public symbols: DummyWebSocket, isolated_social_store, reset_manager_state, test_purge_subject_data_is_noop_for_unknown_subject, test_purge_subject_data_removes_owned_projects_social_rows_jobs_websockets_and_grants
- Internal dependencies (5): backend.api.websocket, backend.config, backend.services.account_purge, backend.services.ownership, backend.services.social.store
- Used by (0): (none detected)

### `backend/tests/test_subtitle_renderer.py`
- Module: `backend.tests.test_subtitle_renderer`
- Purpose: (docstring not found)
- Public symbols: test_burn_subtitles_to_video_can_require_nvenc, test_burn_subtitles_to_video_escapes_filter_path, test_burn_subtitles_to_video_records_nvenc_fallback_forensics, test_generate_ass_file_clamps_word_animation_to_word_duration, test_generate_ass_file_does_not_overlap_dialogue_events_for_multi_chunk_segment, test_generate_ass_file_escapes_ass_control_chars, test_generate_ass_file_prefers_real_word_timestamps_when_segment_text_mismatches, test_generate_ass_file_records_chunk_metrics_and_overflow_status, test_generate_ass_file_rejects_non_list_json, test_generate_ass_file_single_layout_clamps_long_single_word_font, test_generate_ass_file_split_layout_clamps_long_single_word_font, test_generate_ass_file_split_layout_rechunks_unbreakable_heavy_words, test_generate_ass_file_split_layout_uses_line_break_before_overflow, test_generate_ass_file_uses_split_safe_area_header
- Internal dependencies (2): backend.services.subtitle_renderer, backend.services.subtitle_styles
- Used by (0): (none detected)

### `backend/tests/test_subtitle_styles.py`
- Module: `backend.tests.test_subtitle_styles`
- Purpose: Subtitle style ve render spec davranislari icin unit testler.
- Public symbols: TestBackwardCompatibility, TestResolvedRenderSpec, TestStyleManager, TestSubtitleStyle
- Internal dependencies (1): backend.services.subtitle_styles
- Used by (0): (none detected)

### `backend/tests/test_subtitle_timing.py`
- Module: `backend.tests.test_subtitle_timing`
- Purpose: (docstring not found)
- Public symbols: test_chunk_words_merges_very_short_chunks_without_crossing_strong_punctuation, test_compute_word_coverage_ratio_counts_valid_words_against_normalized_tokens, test_normalize_subtitle_text_collapses_unicode_variants, test_snap_segment_boundaries_disables_when_word_coverage_is_low, test_snap_segment_boundaries_uses_word_coverage_gating
- Internal dependencies (1): backend.core.subtitle_timing
- Used by (0): (none detected)

### `backend/tests/test_support_grants.py`
- Module: `backend.tests.test_support_grants`
- Purpose: (docstring not found)
- Public symbols: auth_headers, test_non_owner_cannot_manage_support_grants, test_owner_can_grant_and_revoke_support_access, test_support_subject_must_be_allowlisted
- Internal dependencies (4): backend.api.error_handlers, backend.api.routes, backend.config, backend.services.ownership
- Used by (0): (none detected)

### `backend/tests/test_system_validation.py`
- Module: `backend.tests.test_system_validation`
- Purpose: (docstring not found)
- Public symbols: test_probe_torch_cuda_marks_sandbox_hint, test_run_system_dependency_checks_can_require_gpu, test_run_system_dependency_checks_can_require_nvenc, test_run_system_dependency_checks_treats_gpu_as_optional_by_default, test_summarize_failures_only_returns_required_failures, test_validate_accelerator_support_configuration_requires_gpu_when_enabled
- Internal dependencies (1): backend.system_validation
- Used by (0): (none detected)

### `backend/tests/test_toolchain_contract.py`
- Module: `backend.tests.test_toolchain_contract`
- Purpose: (docstring not found)
- Public symbols: ROOT, test_node_toolchain_contract_is_aligned, test_python_toolchain_contract_is_aligned, test_verify_gate_runs_toolchain_and_runtime_checks
- Internal dependencies (0): (none)
- Used by (0): (none detected)

### `backend/tests/test_video_processor_crop_bounds.py`
- Module: `backend.tests.test_video_processor_crop_bounds`
- Purpose: (docstring not found)
- Public symbols: test_compute_crop_bounds_clamps_left_edge_once, test_compute_crop_bounds_clamps_right_edge
- Internal dependencies (1): backend.services.video_processor
- Used by (0): (none detected)

### `backend/tests/test_video_processor_layout.py`
- Module: `backend.tests.test_video_processor_layout`
- Purpose: (docstring not found)
- Public symbols: test_analyze_opening_shot_reports_delayed_subject_visibility, test_analyze_opening_shot_split_returns_initial_slot_centers, test_build_h264_encoder_args_prefers_cpu_when_nvenc_disabled, test_build_h264_encoder_args_uses_nvenc_when_enabled, test_is_split_layout_stable_accepts_uniformly_distributed_two_person_frames, test_is_split_layout_stable_rejects_close_centers, test_is_split_layout_stable_requires_distribution_across_clip_regions, test_is_split_layout_stable_requires_majority_of_sampled_frames, test_resolve_layout_for_segment_uses_auto_split_when_clip_is_stable, test_stabilize_tracking_center_uses_nearly_static_split_when_tracker_is_weak, test_stabilize_tracking_center_waits_for_split_sustained_motion, test_track_people_falls_back_to_predict_when_lap_is_missing, test_tracking_diagnostics_merge_reports_split_jitter_metrics, test_tracking_stride_uses_sampling_on_cpu_or_predict_fallback, test_video_processor_requires_cuda_when_flag_enabled
- Internal dependencies (1): backend.services.video_processor
- Used by (0): (none detected)

### `backend/tests/test_viral_analyzer_params.py`
- Module: `backend.tests.test_viral_analyzer_params`
- Purpose: backend/tests/test_viral_analyzer_params.py
- Public symbols: TestAnalyzeMetadataParams, TestBuildFallbackSegments
- Internal dependencies (2): backend.services.viral_analyzer, backend.services.viral_analyzer_core
- Used by (0): (none detected)

### `backend/tests/test_viral_analyzer_refactor_guardrails.py`
- Module: `backend.tests.test_viral_analyzer_refactor_guardrails`
- Purpose: Guardrails for ViralAnalyzer refactor boundaries.
- Public symbols: ANALYZER_PATH, CORE_PATH, MAX_ANALYZER_LINES, MAX_METHOD_LINES, TARGET_METHODS, test_analyzer_file_line_budget, test_core_module_exists_and_is_nontrivial, test_target_method_lengths
- Internal dependencies (0): (none)
- Used by (0): (none detected)

### `backend/tests/test_websocket_auth.py`
- Module: `backend.tests.test_websocket_auth`
- Purpose: (docstring not found)
- Public symbols: test_websocket_accepts_bearer_subprotocol_token, test_websocket_accepts_valid_token, test_websocket_rejects_missing_token
- Internal dependencies (1): backend.api.security
- Used by (0): (none detected)

### `backend/tests/test_websocket_subject_isolation.py`
- Module: `backend.tests.test_websocket_subject_isolation`
- Purpose: (docstring not found)
- Public symbols: DummyWebSocket, test_broadcast_progress_reaches_only_matching_subject, test_global_broadcast_reaches_all_connected_subjects
- Internal dependencies (1): backend.api.websocket
- Used by (0): (none detected)

### `backend/tests/test_workflow_helpers.py`
- Module: `backend.tests.test_workflow_helpers`
- Purpose: (docstring not found)
- Public symbols: test_persist_debug_artifacts_marks_missing_overlay_as_partial, test_persist_debug_artifacts_returns_none_when_debug_disabled, test_persist_debug_artifacts_writes_bundle_and_moves_overlay
- Internal dependencies (3): backend.config, backend.core.workflow_helpers, backend.services.ownership
- Used by (0): (none detected)

### `backend/tests/test_workflow_runtime.py`
- Module: `backend.tests.test_workflow_runtime`
- Purpose: (docstring not found)
- Public symbols: test_create_subtitle_renderer_uses_named_style_preset_and_canvas, test_probe_video_canvas_falls_back_to_default_on_error, test_probe_video_canvas_uses_ffprobe, test_resolve_output_video_path_uses_legacy_outputs_without_project, test_resolve_output_video_path_uses_project_outputs_when_project_present, test_resolve_project_master_video_uses_existing_project, test_resolve_project_master_video_uses_owner_scoped_prefix_when_project_missing, test_resolve_subtitle_render_plan_non_short_probes_canvas, test_resolve_subtitle_render_plan_short_uses_video_processor_layout, test_resolve_subtitle_render_plan_uses_lower_third_safe_area_when_detected
- Internal dependencies (3): backend.config, backend.core, backend.services.ownership
- Used by (0): (none detected)

### `backend/tests/test_workflows_batch.py`
- Module: `backend.tests.test_workflows_batch`
- Purpose: (docstring not found)
- Public symbols: test_batch_workflow_includes_partially_overlapping_segments_for_analysis
- Internal dependencies (1): backend.core.workflows_batch
- Used by (0): (none detected)

### `backend/tests/test_workflows_pipeline.py`
- Module: `backend.tests.test_workflows_pipeline`
- Purpose: (docstring not found)
- Public symbols: test_pipeline_ensure_transcript_passes_cancel_event_as_keyword
- Internal dependencies (1): backend.core.workflows_pipeline
- Used by (0): (none detected)

### `backend/tests/test_workflows_refactor_guardrails.py`
- Module: `backend.tests.test_workflows_refactor_guardrails`
- Purpose: Guardrails for workflow module decomposition.
- Public symbols: MODULE_BUDGETS, WORKFLOWS_FACADE, test_workflow_module_line_budgets, test_workflows_facade_is_thin, test_workflows_public_exports_are_stable
- Internal dependencies (1): backend.core.workflows
- Used by (0): (none detected)

### `backend/tests/test_workspace_reset.py`
- Module: `backend.tests.test_workspace_reset`
- Purpose: (docstring not found)
- Public symbols: test_reset_workspace_for_subject_layout_clears_legacy_roots_and_recreates_them, test_reset_workspace_requires_explicit_confirmation
- Internal dependencies (1): backend.config
- Used by (0): (none detected)

### `backend/tests/unit/test_job_lifecycle.py`
- Module: `backend.tests.unit.test_job_lifecycle`
- Purpose: (docstring not found)
- Public symbols: DummyWs, test_job_lifecycle_processing_error, test_job_lifecycle_queued_processing_completed
- Internal dependencies (1): backend.api.websocket
- Used by (0): (none detected)

### `backend/tests/unit/test_upload_prepare_project.py`
- Module: `backend.tests.unit.test_upload_prepare_project`
- Purpose: (docstring not found)
- Public symbols: test_prepare_uploaded_project_isolated_by_subject, test_prepare_uploaded_project_reuses_existing_cached_project, test_prepare_uploaded_project_streams_to_project_dir
- Internal dependencies (3): backend.api.routes.clips, backend.config, backend.services.ownership
- Used by (0): (none detected)

### `backend/tests/unit/test_upload_validation.py`
- Module: `backend.tests.unit.test_upload_validation`
- Purpose: (docstring not found)
- Public symbols: test_stream_upload_to_path_rejects_oversized_payload, test_stream_upload_to_path_writes_bytes_and_returns_hash, test_upload_validation_accepts_supported_type_and_extension, test_upload_validation_rejects_invalid_file
- Internal dependencies (2): backend.api.upload_validation, backend.core.exceptions
- Used by (0): (none detected)

## Frontend Files
### `frontend/src/App.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (4): frontend/src/app/sections.tsx, frontend/src/app/useAppShellController.ts, frontend/src/auth/useResilientAuth.ts, frontend/src/components/ui/SystemStatusBanner.tsx
- Imported by (2): frontend/src/main.tsx, frontend/src/test/App.test.tsx

### `frontend/src/api/client.helpers.ts`
- Purpose: (comment not found)
- Exports: ParsedApiError, extractApiErrorMessage, extractApiErrorPayload, mergeApiHeaders
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/api/client.ts`
- Purpose: frontend/src/api/client.ts
- Exports: accountApi, clipsApi, editorApi, jobsApi, setApiToken, socialApi
- Internal imports (5): frontend/src/api/errors.ts, frontend/src/auth/runtime.ts, frontend/src/auth/session.ts, frontend/src/config.ts, frontend/src/types/index.ts
- Imported by (16): frontend/src/auth/accountCleanup.ts, frontend/src/auth/useResilientAuth.ts, frontend/src/components/AccountDeletionCard.tsx, frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts, frontend/src/components/clipGallery/useClipGalleryController.ts, frontend/src/components/editor/useEditorController.ts, frontend/src/components/jobForm/useJobFormController.ts, frontend/src/components/shareComposer/useShareComposerController.ts, frontend/src/components/subtitleEditor/useSubtitleEditorController.ts, frontend/src/components/ui/lazyVideo/helpers.ts, frontend/src/hooks/useWebSocket.ts, frontend/src/store/useJobStore.ts, frontend/src/test/api/client.helpers.test.ts, frontend/src/test/components/ui/LazyVideo.test.tsx, frontend/src/test/components/ui/lazyVideo.helpers.test.ts, frontend/src/test/components/ui/protectedMedia.test.tsx

### `frontend/src/api/errors.ts`
- Purpose: (comment not found)
- Exports: AppError, AppErrorCode, AppErrorOptions, createAppError, getAppErrorMessage, isAppError
- Internal imports (0): (none)
- Imported by (8): frontend/src/api/client.ts, frontend/src/auth/runtime.ts, frontend/src/auth/useResilientAuth.helpers.ts, frontend/src/auth/useResilientAuth.ts, frontend/src/components/AccountDeletionCard.tsx, frontend/src/components/HoloTerminal.tsx, frontend/src/components/ui/ConnectionChip.tsx, frontend/src/test/auth/useResilientAuth.helpers.test.ts

### `frontend/src/app/helpers.ts`
- Purpose: (comment not found)
- Exports: APP_STATE_STORAGE_KEY, AppState, AppViewMode, DEFAULT_APP_STATE, persistAppState, readAppState
- Internal imports (2): frontend/src/types/index.ts, frontend/src/utils/storage.ts
- Imported by (4): frontend/src/app/sections.tsx, frontend/src/app/useAppShellController.ts, frontend/src/auth/isolation.ts, frontend/src/test/App.test.tsx

### `frontend/src/app/lazyComponents.ts`
- Purpose: (comment not found)
- Exports: AutoCutEditor, Editor, SubtitleEditor, ThreeCanvas
- Internal imports (0): (none)
- Imported by (1): frontend/src/app/sections.tsx

### `frontend/src/app/sections.tsx`
- Purpose: (comment not found)
- Exports: AppBackground, SignedInShell, SignedOutScreen
- Internal imports (13): frontend/src/app/helpers.ts, frontend/src/app/lazyComponents.ts, frontend/src/auth/useResilientAuth.ts, frontend/src/components/AccountDeletionCard.tsx, frontend/src/components/ClipGallery.tsx, frontend/src/components/HoloTerminal.tsx, frontend/src/components/JobForm.tsx, frontend/src/components/JobQueue.tsx, frontend/src/components/SubtitlePreview.tsx, frontend/src/components/ui/ConnectionChip.tsx, frontend/src/components/ui/IconButton.tsx, frontend/src/config/subtitleStyles.ts, frontend/src/types/index.ts
- Imported by (1): frontend/src/App.tsx

### `frontend/src/app/useAppShellController.ts`
- Purpose: (comment not found)
- Exports: useAppShellController
- Internal imports (7): frontend/src/app/helpers.ts, frontend/src/auth/isolation.ts, frontend/src/config/subtitleStyles.ts, frontend/src/hooks/useWebSocket.ts, frontend/src/store/useJobStore.ts, frontend/src/store/useThemeStore.ts, frontend/src/types/index.ts
- Imported by (1): frontend/src/App.tsx

### `frontend/src/auth/accountCleanup.ts`
- Purpose: (comment not found)
- Exports: clearClientAccountState, hardReloadPage
- Internal imports (4): frontend/src/api/client.ts, frontend/src/auth/isolation.ts, frontend/src/auth/runtime.ts, frontend/src/auth/session.ts
- Imported by (1): frontend/src/components/AccountDeletionCard.tsx

### `frontend/src/auth/isolation.ts`
- Purpose: (comment not found)
- Exports: AUTH_IDENTITY_STORAGE_KEY, clearUserScopedClientState, syncIdentityBoundary
- Internal imports (2): frontend/src/app/helpers.ts, frontend/src/auth/session.ts
- Imported by (3): frontend/src/app/useAppShellController.ts, frontend/src/auth/accountCleanup.ts, frontend/src/test/App.test.tsx

### `frontend/src/auth/runtime.ts`
- Purpose: (comment not found)
- Exports: AuthRuntimeState, BackendAuthStatus, useAuthRuntimeStore
- Internal imports (2): frontend/src/api/errors.ts, frontend/src/auth/session.ts
- Imported by (9): frontend/src/api/client.ts, frontend/src/auth/accountCleanup.ts, frontend/src/auth/useResilientAuth.helpers.ts, frontend/src/auth/useResilientAuth.ts, frontend/src/components/HoloTerminal.tsx, frontend/src/components/clipGallery/useClipGalleryController.ts, frontend/src/components/subtitleEditor/useSubtitleEditorController.ts, frontend/src/hooks/useWebSocket.ts, frontend/src/store/useJobStore.ts

### `frontend/src/auth/session.ts`
- Purpose: (comment not found)
- Exports: AUTH_SNAPSHOT_STORAGE_KEY, AuthSnapshot, BuildAuthSnapshotOptions, buildAuthSnapshot, clearAuthSnapshot, getCachedToken, hasOfflineShellAccess, isTokenUsable, readAuthSnapshot, resolveTokenExpiration, writeAuthSnapshot
- Internal imports (2): frontend/src/config.ts, frontend/src/utils/storage.ts
- Imported by (9): frontend/src/api/client.ts, frontend/src/auth/accountCleanup.ts, frontend/src/auth/isolation.ts, frontend/src/auth/runtime.ts, frontend/src/auth/useResilientAuth.helpers.ts, frontend/src/auth/useResilientAuth.ts, frontend/src/test/App.test.tsx, frontend/src/test/auth/session.test.ts, frontend/src/test/auth/useResilientAuth.helpers.test.ts

### `frontend/src/auth/useResilientAuth.helpers.ts`
- Purpose: (comment not found)
- Exports: classifyTokenRefreshError, resolveResilientAuthState, useBootstrapTimeout, useOnlineStatus
- Internal imports (4): frontend/src/api/errors.ts, frontend/src/auth/runtime.ts, frontend/src/auth/session.ts, frontend/src/auth/useResilientAuth.ts
- Imported by (0): (none detected)

### `frontend/src/auth/useResilientAuth.ts`
- Purpose: (comment not found)
- Exports: AuthNotice, ResilientAuthState, ResilientAuthStatus, useResilientAuth
- Internal imports (5): frontend/src/api/client.ts, frontend/src/api/errors.ts, frontend/src/auth/runtime.ts, frontend/src/auth/session.ts, frontend/src/config.ts
- Imported by (5): frontend/src/App.tsx, frontend/src/app/sections.tsx, frontend/src/auth/useResilientAuth.helpers.ts, frontend/src/test/App.test.tsx, frontend/src/test/auth/useResilientAuth.helpers.test.ts

### `frontend/src/components/AccountDeletionCard.tsx`
- Purpose: (comment not found)
- Exports: AccountDeletionCard
- Internal imports (3): frontend/src/api/client.ts, frontend/src/api/errors.ts, frontend/src/auth/accountCleanup.ts
- Imported by (2): frontend/src/app/sections.tsx, frontend/src/test/accountDeletion.test.tsx

### `frontend/src/components/AutoCutEditor.tsx`
- Purpose: (comment not found)
- Exports: AutoCutEditor
- Internal imports (2): frontend/src/components/autoCutEditor/sections.tsx, frontend/src/components/autoCutEditor/useAutoCutEditorController.ts
- Imported by (1): frontend/src/test/components/AutoCutEditor.flow.test.tsx

### `frontend/src/components/ClipGallery.tsx`
- Purpose: (comment not found)
- Exports: ClipGallery
- Internal imports (4): frontend/src/components/ShareComposerModal.tsx, frontend/src/components/clipGallery/sections.tsx, frontend/src/components/clipGallery/useClipGalleryController.ts, frontend/src/types/index.ts
- Imported by (1): frontend/src/app/sections.tsx

### `frontend/src/components/Editor.tsx`
- Purpose: (comment not found)
- Exports: Editor
- Internal imports (2): frontend/src/components/editor/sections.tsx, frontend/src/components/editor/useEditorController.ts
- Imported by (2): frontend/src/test/integration/Editor.api-error.test.tsx, frontend/src/test/integration/Editor.blob-cleanup.test.tsx

### `frontend/src/components/HoloTerminal.tsx`
- Purpose: Most recent log/job determines progress and status
- Exports: HoloTerminal
- Internal imports (4): frontend/src/api/errors.ts, frontend/src/auth/runtime.ts, frontend/src/store/useJobStore.ts, frontend/src/types/index.ts
- Imported by (1): frontend/src/app/sections.tsx

### `frontend/src/components/JobForm.tsx`
- Purpose: (comment not found)
- Exports: JobForm
- Internal imports (2): frontend/src/components/jobForm/sections.tsx, frontend/src/components/jobForm/useJobFormController.ts
- Imported by (1): frontend/src/app/sections.tsx

### `frontend/src/components/JobQueue.tsx`
- Purpose: (comment not found)
- Exports: JobQueue
- Internal imports (2): frontend/src/components/ui/IconButton.tsx, frontend/src/store/useJobStore.ts
- Imported by (1): frontend/src/app/sections.tsx

### `frontend/src/components/RangeSlider.tsx`
- Purpose: (comment not found)
- Exports: RangeSlider
- Internal imports (0): (none)
- Imported by (4): frontend/src/components/autoCutEditor/sections.tsx, frontend/src/components/editor/sections.tsx, frontend/src/components/subtitleEditor/sections.tsx, frontend/src/test/components/RangeSlider.test.tsx

### `frontend/src/components/ShareComposerModal.tsx`
- Purpose: (comment not found)
- Exports: ShareComposerModal
- Internal imports (3): frontend/src/components/shareComposer/sections.tsx, frontend/src/components/shareComposer/useShareComposerController.ts, frontend/src/types/index.ts
- Imported by (1): frontend/src/components/ClipGallery.tsx

### `frontend/src/components/SubtitleEditor.tsx`
- Purpose: (comment not found)
- Exports: SubtitleEditor, SubtitleEditorProps
- Internal imports (3): frontend/src/components/subtitleEditor/sections.tsx, frontend/src/components/subtitleEditor/useSubtitleEditorController.ts, frontend/src/types/index.ts
- Imported by (0): (none detected)

### `frontend/src/components/SubtitlePreview.tsx`
- Purpose: (comment not found)
- Exports: SubtitlePreview
- Internal imports (4): frontend/src/components/subtitlePreview/helpers.ts, frontend/src/components/ui/protectedMedia.ts, frontend/src/config/subtitleStyles.ts, frontend/src/utils/subtitleTiming.ts
- Imported by (3): frontend/src/app/sections.tsx, frontend/src/components/autoCutEditor/sections.tsx, frontend/src/test/components/SubtitlePreview.test.tsx

### `frontend/src/components/ThreeCanvas.tsx`
- Purpose: Yavaşça yıldızları döndür (uzayda süzülme hissi)
- Exports: (none detected)
- Internal imports (1): frontend/src/store/useThemeStore.ts
- Imported by (0): (none detected)

### `frontend/src/components/TimeRangeHeader.tsx`
- Purpose: (comment not found)
- Exports: TimeRangeHeader
- Internal imports (1): frontend/src/utils/time.ts
- Imported by (4): frontend/src/components/autoCutEditor/sections.tsx, frontend/src/components/editor/sections.tsx, frontend/src/components/subtitleEditor/sections.tsx, frontend/src/test/components/TimeRangeHeader.test.tsx

### `frontend/src/components/VideoOverlay.tsx`
- Purpose: (comment not found)
- Exports: VideoOverlay
- Internal imports (5): frontend/src/components/subtitlePreview/helpers.ts, frontend/src/components/videoOverlay/helpers.ts, frontend/src/config/subtitleStyles.ts, frontend/src/types/index.ts, frontend/src/utils/subtitleTiming.ts
- Imported by (2): frontend/src/components/editor/sections.tsx, frontend/src/test/components/VideoOverlay.test.tsx

### `frontend/src/components/autoCutEditor/helpers.ts`
- Purpose: (comment not found)
- Exports: AutoCutJobStateInput, AutoCutJobStateResult, BuildAutoCutPayloadInput, LoadedMetadataRange, MarkerAdditionInput, MarkerAdditionResult, buildAutoCutUploadPayload, deriveAutoCutJobState, getMarkerAdditionResult, getRangeForLoadedMetadata
- Internal imports (2): frontend/src/config/subtitleStyles.ts, frontend/src/types/index.ts
- Imported by (3): frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts, frontend/src/components/autoCutEditor/useAutoCutEditorController.ts, frontend/src/test/components/autoCutEditor.helpers.test.ts

### `frontend/src/components/autoCutEditor/sections.tsx`
- Purpose: (comment not found)
- Exports: AutoCutEditorLayout
- Internal imports (9): frontend/src/components/RangeSlider.tsx, frontend/src/components/SubtitlePreview.tsx, frontend/src/components/TimeRangeHeader.tsx, frontend/src/components/autoCutEditor/useAutoCutEditorController.ts, frontend/src/components/ui/Select.tsx, frontend/src/components/ui/VideoControls.tsx, frontend/src/components/ui/protectedMedia.ts, frontend/src/config/subtitleStyles.ts, frontend/src/utils/time.ts
- Imported by (1): frontend/src/components/AutoCutEditor.tsx

### `frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts`
- Purpose: (comment not found)
- Exports: useAutoCutEditorActions
- Internal imports (3): frontend/src/api/client.ts, frontend/src/components/autoCutEditor/helpers.ts, frontend/src/config/subtitleStyles.ts
- Imported by (2): frontend/src/components/autoCutEditor/useAutoCutEditorController.ts, frontend/src/test/components/autoCutEditor.actions.test.tsx

### `frontend/src/components/autoCutEditor/useAutoCutEditorController.ts`
- Purpose: (comment not found)
- Exports: AutoCutEditorController, useAutoCutEditorController
- Internal imports (10): frontend/src/components/autoCutEditor/helpers.ts, frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts, frontend/src/components/autoCutEditor/useAutoCutEditorLifecycle.ts, frontend/src/components/autoCutEditor/useAutoCutEditorState.ts, frontend/src/config.ts, frontend/src/store/useJobStore.ts, frontend/src/types/index.ts, frontend/src/utils/jobQueue.ts, frontend/src/utils/storage.ts, frontend/src/utils/url.ts
- Imported by (2): frontend/src/components/AutoCutEditor.tsx, frontend/src/components/autoCutEditor/sections.tsx

### `frontend/src/components/autoCutEditor/useAutoCutEditorLifecycle.ts`
- Purpose: (comment not found)
- Exports: usePersistAutoCutSession, useRevokeLocalVideoUrl, useSyncActiveAutoCutJob
- Internal imports (1): frontend/src/store/useJobStore.ts
- Imported by (1): frontend/src/components/autoCutEditor/useAutoCutEditorController.ts

### `frontend/src/components/autoCutEditor/useAutoCutEditorState.ts`
- Purpose: (comment not found)
- Exports: StoredAutoCutSession, useAutoCutEditorState
- Internal imports (1): frontend/src/config/subtitleStyles.ts
- Imported by (1): frontend/src/components/autoCutEditor/useAutoCutEditorController.ts

### `frontend/src/components/clipGallery/sections.tsx`
- Purpose: (comment not found)
- Exports: DeleteClipModal, EmptyState, ErrorState, GalleryHeader, LoadingState, ReadyState
- Internal imports (7): frontend/src/components/clipGallery/useClipGalleryController.ts, frontend/src/components/ui/IconButton.tsx, frontend/src/components/ui/LazyVideo.tsx, frontend/src/components/ui/Select.tsx, frontend/src/components/ui/protectedMedia.ts, frontend/src/types/index.ts, frontend/src/utils/url.ts
- Imported by (1): frontend/src/components/ClipGallery.tsx

### `frontend/src/components/clipGallery/useClipGalleryController.ts`
- Purpose: (comment not found)
- Exports: ClipSortOrder, GalleryState, useClipGalleryController
- Internal imports (4): frontend/src/api/client.ts, frontend/src/auth/runtime.ts, frontend/src/store/useJobStore.ts, frontend/src/types/index.ts
- Imported by (2): frontend/src/components/ClipGallery.tsx, frontend/src/components/clipGallery/sections.tsx

### `frontend/src/components/editor/helpers.ts`
- Purpose: (comment not found)
- Exports: MASTER_EDITOR_SESSION_KEY, ResolvedEditorSessionState, StoredEditorSession, VisibleTranscriptEntry, buildEditorSessionKey, buildStoredEditorSession, clampLoadedMetadataEndTime, filterTranscriptForManualRender, findTranscriptIndexAtTime, formatUploadLimit, getErrorMessage, getTimeRangeError, getVisibleTranscriptEntries, readStoredEditorSession, resolveClipProjectId, resolveEditorVideoSrc, resolveStoredEditorState
- Internal imports (5): frontend/src/config.ts, frontend/src/config/subtitleStyles.ts, frontend/src/types/index.ts, frontend/src/utils/storage.ts, frontend/src/utils/url.ts
- Imported by (3): frontend/src/components/editor/sections.tsx, frontend/src/components/editor/useEditorController.ts, frontend/src/test/components/editor.helpers.test.ts

### `frontend/src/components/editor/sections.tsx`
- Purpose: (comment not found)
- Exports: EditorLayout
- Internal imports (11): frontend/src/components/RangeSlider.tsx, frontend/src/components/TimeRangeHeader.tsx, frontend/src/components/VideoOverlay.tsx, frontend/src/components/editor/helpers.ts, frontend/src/components/editor/useEditorController.ts, frontend/src/components/ui/Select.tsx, frontend/src/components/ui/VideoControls.tsx, frontend/src/components/ui/protectedMedia.ts, frontend/src/config.ts, frontend/src/config/subtitleStyles.ts, frontend/src/utils/time.ts
- Imported by (1): frontend/src/components/Editor.tsx

### `frontend/src/components/editor/useEditorController.ts`
- Purpose: (comment not found)
- Exports: EditorController, EditorProps, useEditorController
- Internal imports (9): frontend/src/api/client.ts, frontend/src/components/editor/helpers.ts, frontend/src/config.ts, frontend/src/config/subtitleStyles.ts, frontend/src/hooks/useDebouncedEffect.ts, frontend/src/hooks/useThrottle.ts, frontend/src/store/useJobStore.ts, frontend/src/types/index.ts, frontend/src/utils/transcript.ts
- Imported by (2): frontend/src/components/Editor.tsx, frontend/src/components/editor/sections.tsx

### `frontend/src/components/jobForm/helpers.ts`
- Purpose: (comment not found)
- Exports: CLIP_COUNT_LIMITS, DEFAULT_AUTO_DURATION_RANGE, DEFAULT_ENGINE, DURATION_LIMITS, ENGINE_OPTIONS, ENGINE_SELECT_OPTIONS, JOB_FORM_PREFS_STORAGE_KEY, LAYOUT_SELECT_OPTIONS, MOTION_SELECT_OPTIONS, RESOLUTION_OPTIONS, STYLE_SELECT_OPTIONS, buildStartJobPayload, clampClipCount, clampDurationSeconds, readInitialAnimationType, readInitialEngine, readInitialLayout, readInitialStyle, resolveDurationRange
- Internal imports (3): frontend/src/config/subtitleStyles.ts, frontend/src/types/index.ts, frontend/src/utils/storage.ts
- Imported by (3): frontend/src/components/jobForm/sections.tsx, frontend/src/components/jobForm/useJobFormController.ts, frontend/src/test/components/jobForm.helpers.test.ts

### `frontend/src/components/jobForm/sections.tsx`
- Purpose: (comment not found)
- Exports: JobFormAutoPilotSection, JobFormControlGridSection, JobFormErrorAlert, JobFormSourceSection, JobFormSubmitButton
- Internal imports (3): frontend/src/components/jobForm/helpers.ts, frontend/src/components/ui/Select.tsx, frontend/src/config/subtitleStyles.ts
- Imported by (1): frontend/src/components/JobForm.tsx

### `frontend/src/components/jobForm/useJobFormController.ts`
- Purpose: (comment not found)
- Exports: JobFormProps, useJobFormController
- Internal imports (4): frontend/src/api/client.ts, frontend/src/components/jobForm/helpers.ts, frontend/src/config/subtitleStyles.ts, frontend/src/store/useJobStore.ts
- Imported by (1): frontend/src/components/JobForm.tsx

### `frontend/src/components/shareComposer/helpers.ts`
- Purpose: (comment not found)
- Exports: DEFAULT_PLATFORM, DraftState, PLATFORM_LABELS, ParsedDraftBuffer, ShareComposerContentMap, buildDraftState, buildHashtagsFromInput, buildPublishTargets, getErrorMessage, getPublishSuccessMessage, localDraftKey, mergeDraftContent, nowPlusHourLocal, parseLocalDraftBuffer, resolveProjectId, summarizePublishErrors, toggleSelection
- Internal imports (1): frontend/src/types/index.ts
- Imported by (4): frontend/src/components/shareComposer/sections.tsx, frontend/src/components/shareComposer/useShareComposerController.ts, frontend/src/test/components/ShareComposerModal.drafts.test.tsx, frontend/src/test/components/shareComposer.helpers.test.ts

### `frontend/src/components/shareComposer/sections.tsx`
- Purpose: (comment not found)
- Exports: ShareComposerLayout
- Internal imports (3): frontend/src/components/shareComposer/helpers.ts, frontend/src/components/shareComposer/useShareComposerController.ts, frontend/src/types/index.ts
- Imported by (1): frontend/src/components/ShareComposerModal.tsx

### `frontend/src/components/shareComposer/useShareComposerController.ts`
- Purpose: Draft autosave best-effort.
- Exports: ShareComposerController, useShareComposerController
- Internal imports (3): frontend/src/api/client.ts, frontend/src/components/shareComposer/helpers.ts, frontend/src/types/index.ts
- Imported by (2): frontend/src/components/ShareComposerModal.tsx, frontend/src/components/shareComposer/sections.tsx

### `frontend/src/components/subtitleEditor/helpers.ts`
- Purpose: (comment not found)
- Exports: EMPTY_CLIP_TRANSCRIPT_CAPABILITIES, SUBTITLE_ANIMATION_OPTIONS, SUBTITLE_STYLE_OPTIONS, SubtitleEditorMode, SubtitleProject, VisibleTranscriptEntry, filterSubtitleProjects, filterVisibleTranscriptEntries, hasSubtitleSelection, replaceTranscriptText, resolveClipSelectValue, resolveCompletionSuccessMessage, resolveLoadedEndTime, resolveSubtitleVideoSrc, resolveTranscriptDuration, selectClipByValue
- Internal imports (4): frontend/src/config.ts, frontend/src/config/subtitleStyles.ts, frontend/src/types/index.ts, frontend/src/utils/url.ts
- Imported by (3): frontend/src/components/subtitleEditor/sections.tsx, frontend/src/components/subtitleEditor/useSubtitleEditorController.ts, frontend/src/test/components/subtitleEditor.helpers.test.ts

### `frontend/src/components/subtitleEditor/sections.tsx`
- Purpose: (comment not found)
- Exports: SubtitleEditorLayout
- Internal imports (9): frontend/src/components/RangeSlider.tsx, frontend/src/components/TimeRangeHeader.tsx, frontend/src/components/subtitleEditor/helpers.ts, frontend/src/components/subtitleEditor/useSubtitleEditorController.ts, frontend/src/components/ui/Select.tsx, frontend/src/components/ui/VideoControls.tsx, frontend/src/components/ui/protectedMedia.ts, frontend/src/types/index.ts, frontend/src/utils/time.ts
- Imported by (1): frontend/src/components/SubtitleEditor.tsx

### `frontend/src/components/subtitleEditor/useSubtitleEditorController.ts`
- Purpose: (comment not found)
- Exports: SubtitleEditorController, UseSubtitleEditorControllerProps, useSubtitleEditorController
- Internal imports (7): frontend/src/api/client.ts, frontend/src/auth/runtime.ts, frontend/src/components/subtitleEditor/helpers.ts, frontend/src/config/subtitleStyles.ts, frontend/src/store/useJobStore.ts, frontend/src/types/index.ts, frontend/src/utils/transcript.ts
- Imported by (2): frontend/src/components/SubtitleEditor.tsx, frontend/src/components/subtitleEditor/sections.tsx

### `frontend/src/components/subtitlePreview/helpers.ts`
- Purpose: (comment not found)
- Exports: PREVIEW_WORDS, PreviewShellType, SubtitlePreviewModel, buildTextShadow, getPreviewBandStyle, getPreviewWordStyle, getSubtitlePreviewModel
- Internal imports (1): frontend/src/config/subtitleStyles.ts
- Imported by (3): frontend/src/components/SubtitlePreview.tsx, frontend/src/components/VideoOverlay.tsx, frontend/src/test/components/subtitlePreview.helpers.test.ts

### `frontend/src/components/ui/ConnectionChip.tsx`
- Purpose: (comment not found)
- Exports: ConnectionChip
- Internal imports (2): frontend/src/api/errors.ts, frontend/src/types/index.ts
- Imported by (2): frontend/src/app/sections.tsx, frontend/src/test/components/ui/ConnectionChip.test.tsx

### `frontend/src/components/ui/IconButton.tsx`
- Purpose: (comment not found)
- Exports: IconButton, IconButtonProps
- Internal imports (0): (none)
- Imported by (4): frontend/src/app/sections.tsx, frontend/src/components/JobQueue.tsx, frontend/src/components/clipGallery/sections.tsx, frontend/src/test/components/ui/IconButton.test.tsx

### `frontend/src/components/ui/LazyVideo.tsx`
- Purpose: (comment not found)
- Exports: LazyVideo
- Internal imports (1): frontend/src/components/ui/protectedMedia.ts
- Imported by (2): frontend/src/components/clipGallery/sections.tsx, frontend/src/test/components/ui/LazyVideo.test.tsx

### `frontend/src/components/ui/Select.tsx`
- Purpose: (comment not found)
- Exports: Select, SelectOption
- Internal imports (0): (none)
- Imported by (6): frontend/src/components/autoCutEditor/sections.tsx, frontend/src/components/clipGallery/sections.tsx, frontend/src/components/editor/sections.tsx, frontend/src/components/jobForm/sections.tsx, frontend/src/components/subtitleEditor/sections.tsx, frontend/src/test/components/ui/Select.test.tsx

### `frontend/src/components/ui/SystemStatusBanner.tsx`
- Purpose: (comment not found)
- Exports: SystemStatusBanner
- Internal imports (0): (none)
- Imported by (1): frontend/src/App.tsx

### `frontend/src/components/ui/VideoControls.tsx`
- Purpose: (comment not found)
- Exports: VideoControls
- Internal imports (0): (none)
- Imported by (4): frontend/src/components/autoCutEditor/sections.tsx, frontend/src/components/editor/sections.tsx, frontend/src/components/subtitleEditor/sections.tsx, frontend/src/test/components/ui/VideoControls.test.tsx

### `frontend/src/components/ui/lazyVideo/helpers.ts`
- Purpose: (comment not found)
- Exports: shouldUseDirectVideoSource
- Internal imports (1): frontend/src/api/client.ts
- Imported by (2): frontend/src/components/ui/protectedMedia.ts, frontend/src/test/components/ui/lazyVideo.helpers.test.ts

### `frontend/src/components/ui/protectedMedia.ts`
- Purpose: Keep the previous blob state keyed by source; stale entries are ignored below.
- Exports: useResolvedMediaSource
- Internal imports (1): frontend/src/components/ui/lazyVideo/helpers.ts
- Imported by (7): frontend/src/components/SubtitlePreview.tsx, frontend/src/components/autoCutEditor/sections.tsx, frontend/src/components/clipGallery/sections.tsx, frontend/src/components/editor/sections.tsx, frontend/src/components/subtitleEditor/sections.tsx, frontend/src/components/ui/LazyVideo.tsx, frontend/src/test/components/ui/protectedMedia.test.tsx

### `frontend/src/components/videoOverlay/helpers.ts`
- Purpose: (comment not found)
- Exports: buildCropGuideStyle, clampCrop, findCurrentSubtitle, findCurrentSubtitleState, getCropFromClientX, getNextCropValue
- Internal imports (3): frontend/src/config/subtitleStyles.ts, frontend/src/types/index.ts, frontend/src/utils/subtitleTiming.ts
- Imported by (2): frontend/src/components/VideoOverlay.tsx, frontend/src/test/components/videoOverlay.helpers.test.ts

### `frontend/src/config.ts`
- Purpose: frontend/src/config.ts
- Exports: API_BASE, API_KEY, API_REQUEST_TIMEOUT_MS, API_RETRY_COUNT, AUTH_BOOTSTRAP_TIMEOUT_MS, AUTH_TOKEN_EXPIRY_SKEW_MS, CLERK_JWT_TEMPLATE, ENABLE_OFFLINE_TOKEN_CACHE, MAX_UPLOAD_BYTES, OFFLINE_AUTH_SNAPSHOT_TTL_MS, WS_BASE
- Internal imports (0): (none)
- Imported by (10): frontend/src/api/client.ts, frontend/src/auth/session.ts, frontend/src/auth/useResilientAuth.ts, frontend/src/components/autoCutEditor/useAutoCutEditorController.ts, frontend/src/components/editor/helpers.ts, frontend/src/components/editor/sections.tsx, frontend/src/components/editor/useEditorController.ts, frontend/src/components/subtitleEditor/helpers.ts, frontend/src/hooks/useWebSocket.ts, frontend/src/utils/url.ts

### `frontend/src/config/subtitleStyles.ts`
- Purpose: (comment not found)
- Exports: ANIMATION_LABELS, ANIMATION_OPTIONS, ANIMATION_REGISTRY, ANIMATION_SELECT_OPTIONS, PreviewAnimationType, PreviewBandVariant, PreviewScreenTheme, RequestedSubtitleLayout, STYLE_LABELS, STYLE_OPTIONS, STYLE_REGISTRY, SUBTITLE_INLINE_STYLES, SUBTITLE_STYLES, StyleName, SubtitleAnimationType, SubtitleInlineStyle, SubtitleLayout, SubtitlePreviewMotion, SubtitleSafeAreaProfile, SubtitleSurface, getSubtitleBoxStyle, isStyleName, isSubtitleAnimationType, resolvePreviewLayout, resolveSubtitleMotion
- Internal imports (0): (none)
- Imported by (20): frontend/src/app/sections.tsx, frontend/src/app/useAppShellController.ts, frontend/src/components/SubtitlePreview.tsx, frontend/src/components/VideoOverlay.tsx, frontend/src/components/autoCutEditor/helpers.ts, frontend/src/components/autoCutEditor/sections.tsx, frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts, frontend/src/components/autoCutEditor/useAutoCutEditorState.ts, frontend/src/components/editor/helpers.ts, frontend/src/components/editor/sections.tsx, frontend/src/components/editor/useEditorController.ts, frontend/src/components/jobForm/helpers.ts, frontend/src/components/jobForm/sections.tsx, frontend/src/components/jobForm/useJobFormController.ts, frontend/src/components/subtitleEditor/helpers.ts, frontend/src/components/subtitleEditor/useSubtitleEditorController.ts, frontend/src/components/subtitlePreview/helpers.ts, frontend/src/components/videoOverlay/helpers.ts, frontend/src/test/config/subtitleStyles.test.ts, frontend/src/utils/subtitleTiming.ts

### `frontend/src/hooks/useDebouncedEffect.ts`
- Purpose: eslint-disable-next-line react-hooks/exhaustive-deps
- Exports: useDebouncedEffect
- Internal imports (0): (none)
- Imported by (2): frontend/src/components/editor/useEditorController.ts, frontend/src/test/hooks/useDebouncedEffect.test.ts

### `frontend/src/hooks/useThrottle.ts`
- Purpose: (comment not found)
- Exports: useThrottledCallback
- Internal imports (0): (none)
- Imported by (2): frontend/src/components/editor/useEditorController.ts, frontend/src/test/hooks/useThrottle.test.ts

### `frontend/src/hooks/useWebSocket.helpers.ts`
- Purpose: (comment not found)
- Exports: MAX_WEBSOCKET_RETRY, RETRY_DELAY_MS, createProgressWebSocket, getConnectStatus, getReconnectState, getWsParseTelemetrySnapshot, parseProgressMessage, resetWsParseTelemetry
- Internal imports (1): frontend/src/types/index.ts
- Imported by (0): (none detected)

### `frontend/src/hooks/useWebSocket.ts`
- Purpose: (comment not found)
- Exports: useWebSocket
- Internal imports (4): frontend/src/api/client.ts, frontend/src/auth/runtime.ts, frontend/src/config.ts, frontend/src/store/useJobStore.ts
- Imported by (3): frontend/src/app/useAppShellController.ts, frontend/src/test/unit/useWebSocket.helpers.test.ts, frontend/src/test/unit/useWebSocket.test.tsx

### `frontend/src/main.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/App.tsx
- Imported by (0): (none detected)

### `frontend/src/store/useJobStore.ts`
- Purpose: Job tamamlandığında artar; ClipGallery yenileme tetikler
- Exports: useJobStore
- Internal imports (3): frontend/src/api/client.ts, frontend/src/auth/runtime.ts, frontend/src/types/index.ts
- Imported by (10): frontend/src/app/useAppShellController.ts, frontend/src/components/HoloTerminal.tsx, frontend/src/components/JobQueue.tsx, frontend/src/components/autoCutEditor/useAutoCutEditorController.ts, frontend/src/components/autoCutEditor/useAutoCutEditorLifecycle.ts, frontend/src/components/clipGallery/useClipGalleryController.ts, frontend/src/components/editor/useEditorController.ts, frontend/src/components/jobForm/useJobFormController.ts, frontend/src/components/subtitleEditor/useSubtitleEditorController.ts, frontend/src/hooks/useWebSocket.ts

### `frontend/src/store/useThemeStore.ts`
- Purpose: (comment not found)
- Exports: useThemeStore
- Internal imports (0): (none)
- Imported by (2): frontend/src/app/useAppShellController.ts, frontend/src/components/ThreeCanvas.tsx

### `frontend/src/test/App.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (5): frontend/src/App.tsx, frontend/src/app/helpers.ts, frontend/src/auth/isolation.ts, frontend/src/auth/session.ts, frontend/src/auth/useResilientAuth.ts
- Imported by (0): (none detected)

### `frontend/src/test/accountDeletion.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/AccountDeletionCard.tsx
- Imported by (0): (none detected)

### `frontend/src/test/api/client.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/api/client.ts
- Imported by (0): (none detected)

### `frontend/src/test/api/client.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/auth/session.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/auth/session.ts
- Imported by (0): (none detected)

### `frontend/src/test/auth/useResilientAuth.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (3): frontend/src/api/errors.ts, frontend/src/auth/session.ts, frontend/src/auth/useResilientAuth.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/AutoCutEditor.flow.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/AutoCutEditor.tsx
- Imported by (0): (none detected)

### `frontend/src/test/components/ClipGallery.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/HoloTerminal.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/JobForm.accessibility.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/JobForm.preferences.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/JobForm.submission.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/RangeSlider.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/RangeSlider.tsx
- Imported by (0): (none detected)

### `frontend/src/test/components/ShareComposerModal.connection.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/ShareComposerModal.drafts.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/shareComposer/helpers.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/ShareComposerModal.publish.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/SubtitleEditor.auth.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/SubtitleEditor.clip.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/SubtitleEditor.project.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/SubtitlePreview.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/SubtitlePreview.tsx
- Imported by (0): (none detected)

### `frontend/src/test/components/TimeRangeHeader.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/TimeRangeHeader.tsx
- Imported by (0): (none detected)

### `frontend/src/test/components/VideoOverlay.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/VideoOverlay.tsx
- Imported by (0): (none detected)

### `frontend/src/test/components/autoCutEditor.actions.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/autoCutEditor/useAutoCutEditorActions.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/autoCutEditor.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (2): frontend/src/components/autoCutEditor/helpers.ts, frontend/src/types/index.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/editor.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (2): frontend/src/components/editor/helpers.ts, frontend/src/types/index.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/jobForm.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/jobForm/helpers.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/jobForm.test-helpers.tsx`
- Purpose: (comment not found)
- Exports: mockFetchJobs, mockStart
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/components/shareComposer.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (2): frontend/src/components/shareComposer/helpers.ts, frontend/src/types/index.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/shareComposer.test-helpers.tsx`
- Purpose: (comment not found)
- Exports: createPrefillResponse, mockApproveJob, mockCancelJob, mockDeleteCredentials, mockDeleteDrafts, mockGetAccounts, mockGetPrefill, mockGetPublishJobs, mockPublish, mockSaveCredentials, mockSaveDrafts, resetShareComposerMocks, shareComposerClip
- Internal imports (1): frontend/src/types/index.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/subtitleEditor.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (2): frontend/src/components/subtitleEditor/helpers.ts, frontend/src/types/index.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/subtitleEditor.test-helpers.tsx`
- Purpose: (comment not found)
- Exports: mockGetClipTranscript, mockGetFreshToken, mockGetProjectTranscript, mockGetProjects, mockListClips, mockProcessManual, mockReburn, mockRecoverClipTranscript, mockRecoverProjectTranscript, mockSaveTranscript, resetSubtitleEditorMocks, storeMock, subtitleClip, subtitleProjects, subtitleTranscript
- Internal imports (1): frontend/src/types/index.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/subtitlePreview.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/subtitlePreview/helpers.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/ui/ConnectionChip.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (2): frontend/src/components/ui/ConnectionChip.tsx, frontend/src/types/index.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/ui/IconButton.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/ui/IconButton.tsx
- Imported by (0): (none detected)

### `frontend/src/test/components/ui/LazyVideo.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (2): frontend/src/api/client.ts, frontend/src/components/ui/LazyVideo.tsx
- Imported by (0): (none detected)

### `frontend/src/test/components/ui/Select.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/ui/Select.tsx
- Imported by (0): (none detected)

### `frontend/src/test/components/ui/VideoControls.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/ui/VideoControls.tsx
- Imported by (0): (none detected)

### `frontend/src/test/components/ui/lazyVideo.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (2): frontend/src/api/client.ts, frontend/src/components/ui/lazyVideo/helpers.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/ui/protectedMedia.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (2): frontend/src/api/client.ts, frontend/src/components/ui/protectedMedia.ts
- Imported by (0): (none detected)

### `frontend/src/test/components/videoOverlay.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/videoOverlay/helpers.ts
- Imported by (0): (none detected)

### `frontend/src/test/config/manualChunks.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/config/subtitleStyles.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/config/subtitleStyles.ts
- Imported by (0): (none detected)

### `frontend/src/test/hooks/useDebouncedEffect.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/hooks/useDebouncedEffect.ts
- Imported by (0): (none detected)

### `frontend/src/test/hooks/useThrottle.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/hooks/useThrottle.ts
- Imported by (0): (none detected)

### `frontend/src/test/integration/Editor.api-error.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/Editor.tsx
- Imported by (0): (none detected)

### `frontend/src/test/integration/Editor.blob-cleanup.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/components/Editor.tsx
- Imported by (0): (none detected)

### `frontend/src/test/setup.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/smoke.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/test/unit/useWebSocket.helpers.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/hooks/useWebSocket.ts
- Imported by (0): (none detected)

### `frontend/src/test/unit/useWebSocket.test.tsx`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/hooks/useWebSocket.ts
- Imported by (0): (none detected)

### `frontend/src/test/utils/subtitleTiming.test.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (1): frontend/src/utils/subtitleTiming.ts
- Imported by (0): (none detected)

### `frontend/src/types/clerk.d.ts`
- Purpose: (comment not found)
- Exports: (none detected)
- Internal imports (0): (none)
- Imported by (0): (none detected)

### `frontend/src/types/index.ts`
- Purpose: frontend/src/types/index.ts
- Exports: AccountDeletionResponse, AccountDeletionSummary, BatchJobPayload, Clip, ClipListResponse, ClipMetadata, ClipTranscriptCapabilities, ClipTranscriptRecoveryPayload, ClipTranscriptResponse, ClipTranscriptStatus, DeleteClipResponse, Job, JobStatus, LogEntry, ManualCutUploadResponse, ManualJobPayload, ProjectSummary, ProjectTranscriptRecoveryPayload, ProjectTranscriptResponse, PublishJob, ReburnPayload, RenderMetadata, RequestedSubtitleLayout, Segment, ShareDraftContent
- Internal imports (0): (none)
- Imported by (36): frontend/src/api/client.ts, frontend/src/app/helpers.ts, frontend/src/app/sections.tsx, frontend/src/app/useAppShellController.ts, frontend/src/components/ClipGallery.tsx, frontend/src/components/HoloTerminal.tsx, frontend/src/components/ShareComposerModal.tsx, frontend/src/components/SubtitleEditor.tsx, frontend/src/components/VideoOverlay.tsx, frontend/src/components/autoCutEditor/helpers.ts, frontend/src/components/autoCutEditor/useAutoCutEditorController.ts, frontend/src/components/clipGallery/sections.tsx, frontend/src/components/clipGallery/useClipGalleryController.ts, frontend/src/components/editor/helpers.ts, frontend/src/components/editor/useEditorController.ts, frontend/src/components/jobForm/helpers.ts, frontend/src/components/shareComposer/helpers.ts, frontend/src/components/shareComposer/sections.tsx, frontend/src/components/shareComposer/useShareComposerController.ts, frontend/src/components/subtitleEditor/helpers.ts

### `frontend/src/utils/jobQueue.ts`
- Purpose: frontend/src/utils/jobQueue.ts
- Exports: getQueuePosition, isProjectBusy
- Internal imports (1): frontend/src/types/index.ts
- Imported by (1): frontend/src/components/autoCutEditor/useAutoCutEditorController.ts

### `frontend/src/utils/storage.ts`
- Purpose: localStorage'dan güvenli JSON okuma.
- Exports: readStored
- Internal imports (0): (none)
- Imported by (5): frontend/src/app/helpers.ts, frontend/src/auth/session.ts, frontend/src/components/autoCutEditor/useAutoCutEditorController.ts, frontend/src/components/editor/helpers.ts, frontend/src/components/jobForm/helpers.ts

### `frontend/src/utils/subtitleTiming.ts`
- Purpose: (comment not found)
- Exports: ActiveSubtitleState, DEFAULT_MAX_CHUNK_DURATION, DEFAULT_MAX_MERGED_CHUNK_DURATION, DEFAULT_MAX_WORDS_PER_SCREEN, DEFAULT_MIN_CHUNK_DURATION, DEFAULT_SPLIT_MAX_WORDS_PER_SCREEN, DEFAULT_WORD_GAP_BREAK, SINGLE_MIN_FONT_SCALE, SMALL_GAP_BRIDGE_THRESHOLD, SPLIT_FONT_CLAMP_MARGIN, SPLIT_HARD_OVERFLOW_RATIO, SPLIT_MIN_FONT_SCALE, SPLIT_SOFT_WRAP_RATIO, SubtitleChunk, SubtitlePlanningOptions, buildSubtitleChunks, findActiveSubtitleState, getSubtitleChunkLines, normalizeSubtitleText, planSubtitleChunkForDisplay
- Internal imports (2): frontend/src/config/subtitleStyles.ts, frontend/src/types/index.ts
- Imported by (4): frontend/src/components/SubtitlePreview.tsx, frontend/src/components/VideoOverlay.tsx, frontend/src/components/videoOverlay/helpers.ts, frontend/src/test/utils/subtitleTiming.test.ts

### `frontend/src/utils/time.ts`
- Purpose: Saniyeyi MM:SS.s formatına çevirir.
- Exports: toMinutesStr, toSecondsStr, toTimeStr
- Internal imports (0): (none)
- Imported by (4): frontend/src/components/TimeRangeHeader.tsx, frontend/src/components/autoCutEditor/sections.tsx, frontend/src/components/editor/sections.tsx, frontend/src/components/subtitleEditor/sections.tsx

### `frontend/src/utils/transcript.ts`
- Purpose: API'den gelen transcript verisini Segment[] formatına normalize eder.
- Exports: normalizeTranscript
- Internal imports (1): frontend/src/types/index.ts
- Imported by (2): frontend/src/components/editor/useEditorController.ts, frontend/src/components/subtitleEditor/useSubtitleEditorController.ts

### `frontend/src/utils/url.ts`
- Purpose: Clip URL'ini güvenli şekilde oluşturur.
- Exports: getClipUrl
- Internal imports (1): frontend/src/config.ts
- Imported by (4): frontend/src/components/autoCutEditor/useAutoCutEditorController.ts, frontend/src/components/clipGallery/sections.tsx, frontend/src/components/editor/helpers.ts, frontend/src/components/subtitleEditor/helpers.ts
