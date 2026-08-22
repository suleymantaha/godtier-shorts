"""Checks that runtime backend imports are represented in requirements.txt files."""

from __future__ import annotations

from pathlib import Path


REQUIREMENTS_PATH = Path(__file__).resolve().parents[2] / "requirements.txt"
API_REQUIREMENTS_PATH = Path(__file__).resolve().parents[2] / "requirements-api.txt"
DIARIZATION_REQUIREMENTS_PATH = Path(__file__).resolve().parents[2] / "requirements-diarization.txt"



def _normalized_requirement_names(path: Path) -> set[str]:
    names: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        package = line.split(";", 1)[0].strip()
        for separator in ("[", ">=", "==", "<=", "~=", "!=", ">", "<"):
            if separator in package:
                package = package.split(separator, 1)[0].strip()
        names.add(package.lower().replace("_", "-"))
    return names



def test_requirements_cover_critical_runtime_dependencies() -> None:
    requirement_names = _normalized_requirement_names(REQUIREMENTS_PATH)

    assert "pyjwt" in requirement_names
    assert "cryptography" in requirement_names
    assert "huggingface-hub" in requirement_names


def test_requirements_cover_production_runtime_dependencies() -> None:
    requirement_names = _normalized_requirement_names(REQUIREMENTS_PATH)

    assert {
        "alembic",
        "arq",
        "asyncpg",
        "boto3",
        "redis",
        "sentry-sdk",
        "sqlalchemy",
    } <= requirement_names


def test_api_requirements_keep_gpu_packages_out_of_control_plane() -> None:
    requirement_names = _normalized_requirement_names(API_REQUIREMENTS_PATH)

    assert {
        "alembic",
        "arq",
        "asyncpg",
        "boto3",
        "redis",
        "sentry-sdk",
        "sqlalchemy",
    } <= requirement_names
    assert {
        "ctranslate2",
        "faster-whisper",
        "opencv-python",
        "torch",
        "torchvision",
        "ultralytics",
    }.isdisjoint(requirement_names)
    assert "yt-dlp" in requirement_names



def test_diarization_requirements_cover_isolated_worker_dependencies() -> None:
    requirement_names = _normalized_requirement_names(DIARIZATION_REQUIREMENTS_PATH)

    assert "pyannote.audio" in requirement_names
    assert "torchaudio" in requirement_names
    assert "soundfile" in requirement_names
    assert "matplotlib" in requirement_names
    assert "transformers" in requirement_names
    assert "speechbrain" in requirement_names
