from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _render_production_compose() -> dict:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI bulunamadi")

    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            "-f",
            "compose.production.yml",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_production_compose_has_private_durable_dependencies() -> None:
    config = _render_production_compose()
    services = config["services"]

    assert set(services) == {"api", "postgres", "redis"}
    assert "ports" not in services["postgres"]
    assert "ports" not in services["redis"]
    assert services["api"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert services["api"]["depends_on"]["redis"]["condition"] == "service_healthy"
    assert config["volumes"]["postgres_data"] is not None


def test_production_api_is_cpu_control_plane_with_readiness_probe() -> None:
    config = _render_production_compose()
    api = config["services"]["api"]

    assert api["environment"]["APP_ENV"] == "production"
    assert api["environment"]["WORKER_MODE"] == "api"
    assert "/health/ready" in " ".join(api["healthcheck"]["test"])
    assert "gpus" not in api
    assert "deploy" not in api


def test_production_api_image_has_bounded_preview_media_tooling() -> None:
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")
    assert "ffmpeg" in dockerfile
