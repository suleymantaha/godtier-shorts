import hashlib
from pathlib import Path
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from backend.api.upload_validation import stream_upload_to_path, validate_upload
from backend.core.exceptions import InvalidInputError


def _upload(filename: str, content_type: str):
    return UploadFile(filename=filename, file=BytesIO(b"123"), headers={"content-type": content_type})


def test_upload_validation_accepts_supported_type_and_extension():
    validate_upload(_upload("video.mp4", "video/mp4"))


@pytest.mark.parametrize("filename,ctype", [("video.exe", "video/mp4"), ("video.mp4", "application/octet-stream")])
def test_upload_validation_rejects_invalid_file(filename, ctype):
    with pytest.raises(HTTPException) as exc:
        validate_upload(_upload(filename, ctype))
    assert exc.value.status_code == 415


def test_stream_upload_to_path_writes_bytes_and_returns_hash(tmp_path: Path):
    payload = b"abc123xyz"
    upload = UploadFile(filename="video.mp4", file=BytesIO(payload), headers={"content-type": "video/mp4"})
    destination = tmp_path / "upload.mp4"

    bytes_written, digest = stream_upload_to_path(upload, destination, max_bytes=1024, chunk_size=3)

    assert bytes_written == len(payload)
    assert digest == hashlib.sha256(payload).hexdigest()
    assert destination.read_bytes() == payload


def test_stream_upload_to_path_rejects_oversized_payload(tmp_path: Path):
    upload = UploadFile(filename="video.mp4", file=BytesIO(b"abcdef"), headers={"content-type": "video/mp4"})

    with pytest.raises(InvalidInputError) as exc:
        stream_upload_to_path(upload, tmp_path / "oversized.mp4", max_bytes=3, chunk_size=2)

    assert "Dosya boyutu çok büyük" in exc.value.message
