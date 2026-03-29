"""Common helpers shared across workflow modules."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
from functools import partial
from pathlib import Path
from typing import Optional

from loguru import logger


class TempArtifactManager:
    """Tracks temporary file paths and removes them on context exit."""

    def __init__(self, *paths: str):
        self._paths = [path for path in paths if path]

    def add(self, path: Optional[str]) -> None:
        if path:
            self._paths.append(path)

    def cleanup(self) -> None:
        for path in self._paths:
            try:
                os.remove(path)
            except FileNotFoundError:
                continue
            except OSError as exc:
                logger.warning("Geçici dosya silinemedi: {} - {}", path, exc)

    def __enter__(self) -> "TempArtifactManager":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()


def build_hook_slug(hook: str, *, max_length: int) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", hook).strip().lower().replace(" ", "_")
    return cleaned[:max_length]


async def run_blocking(func, /, *args, **kwargs):
    """Run a blocking callable inline in tests, otherwise offload to a worker thread."""
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("WORKFLOW_INLINE_BLOCKING") == "1":
        return func(*args, **kwargs)
    return await asyncio.to_thread(partial(func, *args, **kwargs))


def write_json_atomic(path: str | Path, payload: object, *, indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=indent)
        os.replace(temp_path, path)
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass


def move_file_atomic(source: str | Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(str(source), str(destination))


def load_json_dict(path: str | Path) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    return loaded if isinstance(loaded, dict) else None


def hash_file_contents(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_stable_cache_key(payload: dict[str, object]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


__all__ = [
    "TempArtifactManager",
    "build_hook_slug",
    "run_blocking",
    "write_json_atomic",
    "move_file_atomic",
    "load_json_dict",
    "hash_file_contents",
    "build_stable_cache_key",
]
