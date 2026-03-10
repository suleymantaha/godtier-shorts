from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from backend.api.upload_validation import validate_upload


def _upload(filename: str, content_type: str):
    return UploadFile(filename=filename, file=BytesIO(b"123"), headers={"content-type": content_type})


def test_upload_validation_accepts_supported_type_and_extension():
    validate_upload(_upload("video.mp4", "video/mp4"))


@pytest.mark.parametrize("filename,ctype", [("video.exe", "video/mp4"), ("video.mp4", "application/octet-stream")])
def test_upload_validation_rejects_invalid_file(filename, ctype):
    with pytest.raises(HTTPException) as exc:
        validate_upload(_upload(filename, ctype))
    assert exc.value.status_code == 415
