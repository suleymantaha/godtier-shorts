# Repo Deep Scan Diagrams (2026-03-17)

Bu dosya, `repo-deep-scan-2026-03-17.md` raporunun görsel karşılığıdır.

## 1) Katmanlı Sistem Mimarisi

```mermaid
flowchart LR
    subgraph FE["Frontend (React/Vite)"]
        FEAPP["main.tsx / App.tsx"]
        FEUI["components/*"]
        FECFG["config/subtitleStyles.ts"]
        FEWS["hooks/useWebSocket.ts"]
        FEAPI["api/client.ts"]
    end

    subgraph API["FastAPI Layer"]
        SERVER["api/server.py"]
        ROUTES["api/routes/*"]
        AUTH["api/security.py"]
        WS["api/websocket.py"]
    end

    subgraph CORE["Core Orchestration"]
        ORCH["core/orchestrator.py"]
        WFP["workflows_pipeline.py"]
        WFM["workflows_manual.py"]
        WFB["workflows_batch.py"]
        WFR["workflows_reburn.py"]
        HELP["workflow_helpers.py"]
        RUNTIME["workflow_runtime.py"]
        MEDIA["media_ops.py"]
    end

    subgraph SERVICES["Services"]
        STYLES["services/subtitle_styles.py"]
        RENDER["services/subtitle_renderer.py"]
        VP["services/video_processor.py"]
        TR["services/transcription.py"]
        VA["services/viral_analyzer.py"]
        SOC["services/social/*"]
    end

    FEAPP --> FEUI
    FEUI --> FEAPI
    FEUI --> FEWS
    FEUI --> FECFG
    FEAPI --> ROUTES
    FEWS --> WS

    SERVER --> ROUTES
    ROUTES --> AUTH
    ROUTES --> ORCH
    SERVER --> WS

    ORCH --> WFP
    ORCH --> WFM
    ORCH --> WFB
    ORCH --> WFR

    WFP --> HELP
    WFM --> HELP
    WFB --> HELP
    WFR --> HELP
    HELP --> RUNTIME
    HELP --> MEDIA

    RUNTIME --> STYLES
    RUNTIME --> RENDER
    MEDIA --> RENDER
    MEDIA --> VP
    WFP --> TR
    WFP --> VA
    ROUTES --> SOC
```

## 2) Endpoint -> Workflow -> Render Zinciri

```mermaid
flowchart TD
    STARTJOB["POST /api/start-job"] --> RUNGPU["jobs.run_gpu_job"]
    RUNGPU --> RP["orchestrator.run_pipeline_async"]
    RP --> PWF["PipelineWorkflow.run"]
    PWF --> RPS["workflow_helpers.render_pipeline_segments"]
    RPS --> CSR["workflow_runtime.create_subtitle_renderer"]
    CSR --> SS["StyleManager.resolve_style + resolve_render_spec"]
    RPS --> GEN["SubtitleRenderer.generate_ass_file"]
    RPS --> BURN["SubtitleRenderer.burn_subtitles_to_video"]

    MANUAL["POST /api/manual-cut-upload"] --> M1["orchestrator.run_manual_clip_async / run_manual_clips_from_cut_points_async / run_batch_manual_clips_async"]
    M1 --> MW["Manual/CutPoints/Batch Workflow"]
    MW --> RPS

    REBURN["POST /api/reburn"] --> RB["orchestrator.reburn_subtitles_async"]
    RB --> RWF["ReburnWorkflow.run"]
    RWF --> GEN
    RWF --> BURN
```

## 3) Subtitle Pipeline Fonksiyon Bağımlılık Haritası

```mermaid
flowchart LR
    RTPLAN["resolve_subtitle_render_plan()"]
    CREATE["create_subtitle_renderer()"]
    RESOLVE_STYLE["StyleManager.resolve_style()"]
    RESOLVE_SPEC["StyleManager.resolve_render_spec()"]
    GEN_ASS["SubtitleRenderer.generate_ass_file()"]
    TIMING["core/subtitle_timing.py"]
    BURN["SubtitleRenderer.burn_subtitles_to_video()"]
    FFMPEG["ffmpeg (NVENC -> CPU fallback)"]
    META["render_metadata.subtitle_layout_quality"]

    RTPLAN --> CREATE
    CREATE --> RESOLVE_STYLE
    CREATE --> RESOLVE_SPEC
    RESOLVE_STYLE --> GEN_ASS
    RESOLVE_SPEC --> GEN_ASS
    TIMING --> GEN_ASS
    GEN_ASS --> BURN
    BURN --> FFMPEG
    GEN_ASS --> META
    BURN --> META
```

## 4) Frontend Subtitle Konfigürasyon Etki Grafiği

```mermaid
flowchart LR
    CFG["frontend/src/config/subtitleStyles.ts"]
    JOBFORM["components/JobForm*"]
    PREVIEW["components/SubtitlePreview*"]
    OVERLAY["components/VideoOverlay*"]
    APPCTL["app/useAppShellController.ts"]
    UTILS["utils/subtitleTiming.ts"]
    TESTS["frontend/src/test/config/subtitleStyles.test.ts + ilgili component testleri"]

    CFG --> JOBFORM
    CFG --> PREVIEW
    CFG --> OVERLAY
    CFG --> APPCTL
    CFG --> UTILS
    CFG --> TESTS
```

## 5) Tarama Artifact İlişkisi

```mermaid
flowchart LR
    SUMMARY["repo-deep-scan-2026-03-17.md"]
    APPX["repo-deep-scan-2026-03-17-appendix.md"]
    DIAG["repo-deep-scan-2026-03-17-diagrams.md"]

    SUMMARY --> APPX
    SUMMARY --> DIAG
```
