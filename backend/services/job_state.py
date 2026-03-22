from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

RUNTIME_ONLY_KEYS = {"cancel_event", "task", "task_handle"}
RECOVERABLE_STATUSES = {"queued", "processing"}
MAX_JOB_TIMELINE_ENTRIES = 300


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobRecord(dict[str, Any]):
    def __init__(self, initial: dict[str, Any], *, on_change: callable) -> None:
        super().__init__(initial)
        self._on_change = on_change

    def rebind(self, on_change: callable) -> None:
        self._on_change = on_change

    def _changed(self) -> None:
        self._on_change()

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        self._changed()

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        self._changed()

    def clear(self) -> None:
        super().clear()
        self._changed()

    def pop(self, key: str, default: Any = None) -> Any:
        if key in self:
            value = super().pop(key)
            self._changed()
            return value
        return default

    def popitem(self) -> tuple[str, Any]:
        item = super().popitem()
        self._changed()
        return item

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key in self:
            return self[key]
        value = super().setdefault(key, default)
        self._changed()
        return value

    def update(self, *args: Any, **kwargs: Any) -> None:
        super().update(*args, **kwargs)
        self._changed()


class JobStateRepository(dict[str, JobRecord]):
    def __init__(self, storage_path: Path | None = None) -> None:
        self._storage_path = storage_path
        self._lock = threading.RLock()
        self._suspend_persist = False
        super().__init__()
        if storage_path is not None:
            self._load_from_disk()

    def __setitem__(self, job_id: str, value: dict[str, Any]) -> None:
        with self._lock:
            super().__setitem__(job_id, self._wrap_record(job_id, value))
            self._persist_locked()

    def __delitem__(self, job_id: str) -> None:
        with self._lock:
            super().__delitem__(job_id)
            self._persist_locked()

    def clear(self) -> None:
        with self._lock:
            super().clear()
            self._persist_locked()

    def pop(self, job_id: str, default: Any = None) -> Any:
        with self._lock:
            if job_id in self:
                value = super().pop(job_id)
                self._persist_locked()
                return value
            return default

    def popitem(self) -> tuple[str, JobRecord]:
        with self._lock:
            item = super().popitem()
            self._persist_locked()
            return item

    def setdefault(self, job_id: str, default: dict[str, Any] | None = None) -> JobRecord:
        with self._lock:
            if job_id in self:
                return super().__getitem__(job_id)
            record = self._wrap_record(job_id, default or {})
            super().__setitem__(job_id, record)
            self._persist_locked()
            return record

    def update(self, *args: Any, **kwargs: Any) -> None:
        payload = dict(*args, **kwargs)
        with self._lock:
            for job_id, value in payload.items():
                super().__setitem__(job_id, self._wrap_record(job_id, value))
            self._persist_locked()

    def _wrap_record(self, job_id: str, value: dict[str, Any]) -> JobRecord:
        if isinstance(value, JobRecord):
            value.rebind(self._persist)
            value.setdefault("job_id", job_id)
            return value
        record = JobRecord(dict(value), on_change=self._persist)
        record.setdefault("job_id", job_id)
        return record

    def _persist(self) -> None:
        with self._lock:
            self._persist_locked()

    def _persist_locked(self) -> None:
        if self._suspend_persist or self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "jobs": {
                job_id: self._serialize_record(record)
                for job_id, record in self.items()
            },
        }
        temp_path = self._storage_path.with_suffix(f"{self._storage_path.suffix}.tmp")
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        temp_path.replace(self._storage_path)

    @staticmethod
    def _serialize_record(record: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in record.items()
            if key not in RUNTIME_ONLY_KEYS
        }

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return

        try:
            with open(self._storage_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Job state yüklenemedi: {}", exc)
            return

        jobs_payload = payload.get("jobs", {}) if isinstance(payload, dict) else {}
        if not isinstance(jobs_payload, dict):
            logger.warning("Job state dosyası beklenen formatta değil: {}", self._storage_path)
            return

        self._suspend_persist = True
        try:
            for job_id, raw in jobs_payload.items():
                if not isinstance(raw, dict):
                    continue
                super().__setitem__(job_id, self._wrap_record(job_id, self._normalize_loaded_job(job_id, raw)))
        finally:
            self._suspend_persist = False

        self._persist()

    @staticmethod
    def _normalize_loaded_job(job_id: str, raw: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(raw)
        normalized.setdefault("job_id", job_id)

        status = str(normalized.get("status") or "")
        if status not in RECOVERABLE_STATUSES:
            return normalized

        message = "İş sunucu yeniden başlatıldığı için kesildi."
        progress = int(normalized.get("progress") or 0)
        timeline = list(normalized.get("timeline") or [])
        timeline.append(
            {
                "id": f"{job_id}:recovered",
                "at": _utc_now_iso(),
                "job_id": job_id,
                "status": "error",
                "progress": progress,
                "message": message,
                "source": "api",
            }
        )
        normalized["timeline"] = timeline[-MAX_JOB_TIMELINE_ENTRIES:]
        normalized["status"] = "error"
        normalized["error"] = message
        normalized["last_message"] = message
        return normalized
