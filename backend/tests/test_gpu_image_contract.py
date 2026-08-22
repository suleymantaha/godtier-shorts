from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_gpu_image_requires_accelerators_and_persistent_model_caches() -> None:
    dockerfile = (ROOT / "Dockerfile.gpu").read_text(encoding="utf-8")

    assert "REQUIRE_CUDA_FOR_APP=1" in dockerfile
    assert "REQUIRE_NVENC_FOR_APP=1" in dockerfile
    assert "GODTIER_WORKSPACE=/scratch/workspace" in dockerfile
    assert "GODTIER_MODELS_DIR=/models" in dockerfile
    assert "YOLO_CONFIG_DIR=/models/ultralytics" in dockerfile
    assert "VOLUME [\"/models\", \"/scratch\"]" in dockerfile
    assert "docker/gpu-entrypoint.sh" in dockerfile
    assert "import ctranslate2, torch, ultralytics" in dockerfile
    assert "grep -q h264_nvenc" in dockerfile
    assert "python -m pip install -r requirements.lock" in dockerfile


def test_gpu_entrypoint_runs_validation_before_arq_worker() -> None:
    entrypoint = (ROOT / "docker/gpu-entrypoint.sh").read_text(encoding="utf-8")

    assert "backend.workers.gpu_entrypoint" in entrypoint
    assert "exec python -m arq backend.workers.gpu_worker.WorkerSettings" in entrypoint
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attributes
