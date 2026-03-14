from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import HTTPException, UploadFile

from backend.config import UPLOAD_MAX_FILE_SIZE
from backend.core.exceptions import InvalidInputError

ALLOWED_UPLOAD_MIME_TYPES = {"video/mp4", "video/quicktime", "video/x-m4v"}
ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".m4v"}
DEFAULT_UPLOAD_CHUNK_SIZE = 1024 * 1024


def _bytes_to_mb(size_in_bytes: int) -> int:
    """Byte değerini MB cinsine çevirir."""
    return size_in_bytes // (1024 * 1024)


def validate_upload(file: UploadFile) -> None:
    filename = (file.filename or "").strip().lower()
    extension = filename[filename.rfind(".") :] if "." in filename else ""
    content_type = (file.content_type or "").lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Geçersiz dosya uzantısı")

    if content_type and content_type not in ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Desteklenmeyen dosya türü")


def validate_upload_size(file: UploadFile) -> None:
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > UPLOAD_MAX_FILE_SIZE:
        raise InvalidInputError(f"Dosya boyutu çok büyük. Maksimum: {_bytes_to_mb(UPLOAD_MAX_FILE_SIZE)}MB")


def stream_upload_to_path(
    file: UploadFile,
    destination_path: str | Path,
    *,
    max_bytes: int = UPLOAD_MAX_FILE_SIZE,
    chunk_size: int = DEFAULT_UPLOAD_CHUNK_SIZE,
) -> tuple[int, str]:
    """Upload içeriğini tek geçişte diske yazar, boyutu denetler ve SHA256 hesaplar."""
    try:
        file.file.seek(0)
    except (AttributeError, OSError):
        pass

    total_bytes = 0
    sha = hashlib.sha256()
    path = Path(destination_path)

    with path.open("wb") as output_file:
        while True:
            chunk = file.file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise InvalidInputError(
                    f"Dosya boyutu çok büyük. Maksimum: {_bytes_to_mb(max_bytes)}MB"
                )
            sha.update(chunk)
            output_file.write(chunk)

    return total_bytes, sha.hexdigest()
