"""Resolve external CLI tool executables in a venv-aware way.

Windows'ta `python -m backend.main` gibi bir başlangıç komutu venv `Scripts`
dizinini PATH'e otomatik eklemez. Bu nedenle subprocess çağrılarında ham
`"yt-dlp"` / `"ffmpeg"` / `"ffprobe"` adları `[WinError 2] Sistem belirtilen
dosyayı bulamıyor` hatasına yol açabiliyor.

Bu modül; çağrı yerlerinde değişiklik gerektirmeden çalışacak hafif bir
çözümleyici sağlar. Sıralama:

1. ``sys.executable`` klasörü (venv Scripts/bin) — venv aktif olmasa bile
   bulunur, çünkü backend o python ile başlatıldı.
2. ``BACKEND_TOOL_BIN_DIRS`` env değişkeninde tanımlı ek dizinler (PATHSEP).
3. ``shutil.which`` (global PATH).
4. Bulunamazsa ham adı geri döndür (geriye dönük uyumluluk + test mock'ları).
"""

from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path

_WINDOWS_EXECUTABLE_EXTS: tuple[str, ...] = (".exe", ".cmd", ".bat")


def _candidate_bin_dirs() -> list[Path]:
    dirs: list[Path] = []
    seen: set[str] = set()

    def _push(candidate: Path | str | None) -> None:
        if not candidate:
            return
        path = Path(candidate)
        if not path:
            return
        key = str(path).lower() if os.name == "nt" else str(path)
        if key in seen:
            return
        seen.add(key)
        dirs.append(path)

    python_executable = sys.executable
    if python_executable:
        _push(Path(python_executable).resolve().parent)

    extra_dirs_raw = os.environ.get("BACKEND_TOOL_BIN_DIRS", "").strip()
    if extra_dirs_raw:
        for entry in extra_dirs_raw.split(os.pathsep):
            entry = entry.strip()
            if entry:
                _push(entry)

    return dirs


def _executable_extensions() -> tuple[str, ...]:
    if os.name != "nt":
        return ("",)
    pathext = os.environ.get("PATHEXT", "")
    raw_extensions = [ext.strip().lower() for ext in pathext.split(os.pathsep) if ext.strip()]
    extensions: list[str] = [""]
    for ext in (*_WINDOWS_EXECUTABLE_EXTS, *raw_extensions):
        if ext and ext not in extensions:
            extensions.append(ext)
    return tuple(extensions)


def _find_in_directories(name: str, directories: list[Path]) -> str | None:
    for directory in directories:
        try:
            if not directory.is_dir():
                continue
        except OSError:
            continue
        for ext in _executable_extensions():
            candidate = directory / f"{name}{ext}"
            try:
                if candidate.is_file():
                    return str(candidate)
            except OSError:
                continue
    return None


@lru_cache(maxsize=64)
def resolve_tool(name: str) -> str:
    """Return the best executable path for *name* (or *name* itself if missing)."""
    if not name:
        return name

    if os.path.sep in name or (os.name == "nt" and "/" in name):
        return name

    discovered = _find_in_directories(name, _candidate_bin_dirs())
    if discovered:
        return discovered

    which_result = shutil.which(name)
    if which_result:
        return which_result

    return name


def clear_resolve_cache() -> None:
    """Test/debug yardımcı: çözümleyici cache'ini sıfırla."""
    resolve_tool.cache_clear()


def ytdlp() -> str:
    return resolve_tool("yt-dlp")


def ffmpeg() -> str:
    return resolve_tool("ffmpeg")


def ffprobe() -> str:
    return resolve_tool("ffprobe")
