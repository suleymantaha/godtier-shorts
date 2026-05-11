#!/usr/bin/env python3
"""Download Systran faster-whisper weights into models/whisper-{size}/ (see transcription.py)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from huggingface_hub import snapshot_download

from backend.config import MODELS_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Systran faster-whisper into MODELS_DIR.")
    parser.add_argument("--model-size", default="large-v3", help="Model suffix (default: large-v3)")
    args = parser.parse_args()

    repo_id = f"Systran/faster-whisper-{args.model_size}"
    local_dir = MODELS_DIR / f"whisper-{args.model_size}"

    token = os.environ.get("HF_TOKEN", "").strip() or None

    print(f"Hedef: {local_dir}")
    print(f"Repo: {repo_id}")

    local_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(local_dir),
        token=token,
    )
    print("Tamam.")


if __name__ == "__main__":
    main()
