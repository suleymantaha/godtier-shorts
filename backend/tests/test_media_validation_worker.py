from __future__ import annotations

from uuid import uuid4

import pytest

from backend.workers import media_validation


class FakeR2Client:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def download_file(self, bucket, key, filename):
        assert bucket == "private-assets"
        assert key.startswith("uploads/")
        with open(filename, "wb") as target:
            target.write(self.payload)


@pytest.mark.asyncio
async def test_media_validation_worker_downloads_to_scratch_and_runs_ffprobe(
    monkeypatch,
) -> None:
    payload = b"valid-video"
    user_id = uuid4()
    storage_key = f"uploads/{user_id}/{uuid4()}.mp4"
    monkeypatch.setattr(
        media_validation,
        "probe_media",
        lambda _path: {
            "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            "streams": [{"codec_type": "video"}],
        },
    )

    result = await media_validation.validate_uploaded_media(
        {"r2_client": FakeR2Client(payload), "r2_bucket_name": "private-assets"},
        str(user_id),
        storage_key,
        "video/mp4",
        len(payload),
    )

    assert result["status"] == "validated"
    assert result["storage_key"] == storage_key


def test_media_validation_rejects_file_without_video_stream() -> None:
    with pytest.raises(ValueError, match="no video stream"):
        media_validation.validate_probe_result(
            {"format": {"format_name": "mp4"}, "streams": [{"codec_type": "audio"}]}
        )
