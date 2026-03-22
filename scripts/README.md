# scripts/

Yardımcı ve integration scriptleri. Unit testler `backend/tests/` ve `frontend/src/**/*.test.*` altındadır.

| Script | Açıklama |
|--------|----------|
| `verify.sh` | Kök kalite kapısı. Toolchain check + runtime config check + frontend `lint + test + build` ve backend `pytest backend/tests -q` adımlarını fail-fast çalıştırır. |
| `check_coverage.sh` | Backend için `pytest-cov`, frontend için Vitest coverage çalıştırır; repo threshold'larını enforce eder ve coverage artifact'larını üretir. |
| `check_markdown_links.py` | `docs/` ve kök `README.md` içindeki yerel markdown linklerini doğrular. `python scripts/check_markdown_links.py` |
| `check_toolchain.py` | Yerel Python/Node/npm sürümlerini ve repo içi sürüm sözleşmesini (`.python-version`, `.nvmrc`, pyright/pyre, CI) doğrular. |
| `check_runtime_config.py` | `.env` yükleyip runtime config değerlerini doğrular; hatalı URL/port/limit değerlerinde erken fail eder. |
| `check_system_deps.py` | `ffmpeg`, `yt-dlp`, `nvidia-smi` ve `torch.cuda` durumunu denetler. Varsayılan modda GPU opsiyoneldir; `--require-gpu` ile CUDA varlığı, `--require-nvenc` ile `ffmpeg h264_nvenc` smoke testi zorunlu yapılabilir. Sandbox altında yalancı negatif görebilir; prod/backend runtime doğrulaması için `run.sh` veya gerçek host shell kullanın. |
| `generate_requirements_lock.py` | `requirements.txt` içindeki doğrudan bağımlılıkları kurulu sürümlere pinleyerek `requirements.lock` üretir. |
| `update_requirements_lock.sh` | `requirements.txt` içinden pinlenmiş `requirements.lock` üretir. `bash scripts/update_requirements_lock.sh` |
| `audit_python_deps.sh` | `requirements.lock` üzerinden Python dependency audit çalıştırır. `bash scripts/audit_python_deps.sh` |
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

## GPU Startup Politikası

- `run.sh` varsayılan olarak `PYTORCH_NVML_BASED_CUDA_CHECK=1`, `CUDA_DEVICE_ORDER=PCI_BUS_ID` ve `LOG_ACCELERATOR_STATUS_ON_STARTUP=1` export eder.
- Ortam aktivasyonu sırası: mevcut aktif env, `APP_ENV_NAME` ile verilen Conda env, proje kökündeki `.venv`, proje kökündeki `venv`, son olarak sistem `python`/`npm`.
- `SKIP_ENV_ACTIVATION=1 ./run.sh` ile otomatik env aktivasyonu tamamen kapatılabilir.
- `REQUIRE_CUDA_FOR_APP=1` ise backend startup ve YOLO model yükleme sırasında CUDA zorunlu olur; sessiz CPU fallback yapılmaz.
- `REQUIRE_NVENC_FOR_APP=1` ise startup önkontrolü `check_system_deps.py --require-nvenc` ile fail-fast çalışır.
- Subtitle burn için ayrı sıkı mod: `REQUIRE_NVENC_FOR_BURN=1`.
- Frontend dev server `ENOSPC` watcher hatası verirse `run.sh` otomatik olarak `CHOKIDAR_USEPOLLING=1` ve varsayılan `CHOKIDAR_INTERVAL=300` ile polling fallback moduna geçer.

## Benchmark Raporu

- `benchmark_render_stability.py` raporunu `workspace/logs/render_benchmarks/` altına JSON olarak yazar.
- Temel alanlar: `deterministic`, `run_count`, `render_wall_ms`, `throughput_fps`, `frame_hash_matches`, `metadata_matches`, `rss_mb_peak`, `debug_environment`.

## Dependency Locking

- Lock dosyası: `requirements.lock`
- Güncelleme akışı:
  - `python -m pip install pip-audit`
  - `bash scripts/update_requirements_lock.sh`
  - `bash scripts/audit_python_deps.sh`
- `requirements.txt` intent/üst sınır kaynağı, `requirements.lock` ise tekrarlanabilir kurulum girdisi olarak tutulur.
