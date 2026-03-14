"""Shared helpers for orchestrator workflow modules."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass(frozen=True)
class ProgressStepMapper:
    """Maps iterative steps into a bounded progress range."""

    start: int
    end: int
    total_steps: int

    def map(self, step_index: int) -> int:
        if self.total_steps <= 0:
            return self.end
        bounded = min(max(step_index, 0), self.total_steps)
        delta = self.end - self.start
        return self.start + int((bounded / self.total_steps) * delta)


class TempArtifactManager:
    """Tracks temporary file paths and removes them on context exit."""

    def __init__(self, *paths: str):
        self._paths = [p for p in paths if p]

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
