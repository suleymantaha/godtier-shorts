from fastapi import HTTPException, UploadFile

from backend.config import UPLOAD_MAX_FILE_SIZE
from backend.core.exceptions import InvalidInputError

ALLOWED_UPLOAD_MIME_TYPES = {"video/mp4", "video/quicktime", "video/x-m4v"}
ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".m4v"}


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
