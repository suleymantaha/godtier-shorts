# scripts/

Yardımcı ve integration scriptleri. Unit testler `backend/tests/` ve `frontend/src/**/*.test.*` altındadır.

| Script | Açıklama |
|--------|----------|
| `verify.sh` | Kök kalite kapısı. Toolchain check + runtime config check + frontend `lint + test + build` ve backend `pytest backend/tests -q` adımlarını fail-fast çalıştırır. |
| `check_toolchain.py` | Yerel Python/Node/npm sürümlerini ve repo içi sürüm sözleşmesini (`.python-version`, `.nvmrc`, pyright/pyre, CI) doğrular. |
| `check_runtime_config.py` | `.env` yükleyip runtime config değerlerini doğrular; hatalı URL/port/limit değerlerinde erken fail eder. |
| `check_system_deps.py` | `ffmpeg`, `yt-dlp`, `nvidia-smi` ve `torch.cuda` durumunu denetler. Varsayılan modda GPU opsiyoneldir; `--require-gpu` ile zorunlu yapılabilir. |
| `test_subtitle_styles.py` | Altyazı stilleri ASS üretimini gerçek proje ile test eder. `python scripts/test_subtitle_styles.py [PROJECT_DIR]` |
| `ass_format_example.py` | ASS pop/fade override string örnekleri. |
| `reburn_clip.py` | Klibe yeni layout/stil uygular. `python scripts/reburn_clip.py --project ID --clip NAME [--layout split] [--style HORMOZI]` |
| `benchmark_render_stability.py` | Aynı klibi tekrar render ederek determinism ve throughput raporu üretir. `python scripts/benchmark_render_stability.py --project ID --clip NAME [--runs 3 --samples 5]` |
| `check_orphan_legacy.py` | Legacy/orphan script/import guard. CI içinde çalışır ve kanonik yol olarak `backend.services.subtitle_renderer` kullanımını zorlar. |
| `run_pyre.sh` | Pyre çalıştırıcı wrapper. `PYRE_PYTHON_INTERPRETER` ve `PYRE_SITE_PACKAGES` env'leri opsiyoneldir. |
| `quarantine_legacy_projects.py` | Ownership manifesti olmayan `workspace/projects/*` dizinlerini tek seferlik `quarantined` manifest ile kapatır. `python scripts/quarantine_legacy_projects.py` |

## Debug Artifact Notu

- `DEBUG_RENDER_ARTIFACTS=1` ile clip render'larında proje içine `debug/<clip_stem>/` bundle'ı yazılır.
- Bundle içeriği: `tracking_overlay.mp4`, `tracking_timeline.json`, `subtitle_chunks.json`, `boundary_snap.json`, `timing_report.json`.
- Bu artifact'lar tanı amaçlıdır; clip transcript metadata içinden proje-göreli path olarak referanslanır.

## Benchmark Raporu

- `benchmark_render_stability.py` raporunu `workspace/logs/render_benchmarks/` altına JSON olarak yazar.
- Temel alanlar: `deterministic`, `run_count`, `render_wall_ms`, `throughput_fps`, `frame_hash_matches`, `metadata_matches`, `rss_mb_peak`, `debug_environment`.
