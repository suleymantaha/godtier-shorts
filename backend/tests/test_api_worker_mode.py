from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_api_worker_mode_imports_without_gpu_runtime_packages() -> None:
    script = r"""
import importlib.abc
import sys

blocked = {
    "cv2",
    "ctranslate2",
    "faster_whisper",
    "torch",
    "torchvision",
    "ultralytics",
}

class BlockGpuImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in blocked:
            raise ImportError(f"blocked GPU runtime import: {fullname}")
        return None

sys.meta_path.insert(0, BlockGpuImports())

from backend.api.server import create_app

paths = set(create_app().openapi()["paths"])
assert "/health/live" in paths
assert "/health/ready" in paths
assert "/api/start-job" in paths
"""
    env = os.environ.copy()
    env["APP_ENV"] = "development"
    env["WORKER_MODE"] = "api"

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
