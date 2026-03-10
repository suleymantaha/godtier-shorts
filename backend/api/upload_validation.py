from fastapi import HTTPException, UploadFile

from backend.config import UPLOAD_MAX_FILE_SIZE
from backend.core.exceptions import InvalidInputError

ALLOWED_UPLOAD_TYPES = {"video/mp4", "video/quicktime", "video/x-matroska", "video/webm"}


def _bytes_to_mb(size_in_bytes: int) -> int:
    """Byte değerini MB cinsine çevirir."""
    return size_in_bytes // (1024 * 1024)


def validate_upload(file: UploadFile) -> None:
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=415, detail="Desteklenmeyen dosya türü")

    if file.filename and not file.filename.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
        raise HTTPException(status_code=415, detail="Geçersiz dosya uzantısı")


def validate_upload_size(file: UploadFile) -> None:
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > UPLOAD_MAX_FILE_SIZE:
        raise InvalidInputError(f"Dosya boyutu çok büyük. Maksimum: {_bytes_to_mb(UPLOAD_MAX_FILE_SIZE)}MB")
