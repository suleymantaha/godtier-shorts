from __future__ import annotations

import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID

from backend.core.render_quality import probe_media
from backend.services.storage.object_store import validate_upload_metadata


ALLOWED_CONTAINERS = {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}


def validate_probe_result(probe_data: dict[str, Any]) -> None:
    format_data = probe_data.get("format")
    streams = probe_data.get("streams")
    if not isinstance(format_data, dict) or not isinstance(streams, list):
        raise ValueError("Invalid media probe result")
    format_names = {
        item.strip().lower()
        for item in str(format_data.get("format_name") or "").split(",")
        if item.strip()
    }
    if format_names.isdisjoint(ALLOWED_CONTAINERS):
        raise ValueError("Unsupported media container")
    if not any(
        isinstance(stream, dict) and stream.get("codec_type") == "video"
        for stream in streams
    ):
        raise ValueError("Uploaded media has no video stream")


def _create_r2_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


async def validate_uploaded_media(
    ctx: dict[str, Any],
    user_id: str,
    storage_key: str,
    content_type: str,
    size_bytes: int,
) -> dict[str, Any]:
    """Download an upload to worker scratch and validate it with ffprobe."""
    parsed_user_id = UUID(user_id)
    prefix = f"uploads/{parsed_user_id}/"
    if not storage_key.startswith(prefix) or "/" in storage_key[len(prefix) :]:
        raise ValueError("Upload key does not belong to user")
    validate_upload_metadata(
        Path(storage_key).name,
        content_type,
        size_bytes,
        int(os.getenv("UPLOAD_MAX_FILE_SIZE", str(5 * 1024 * 1024 * 1024))),
    )

    client = ctx.get("r2_client") or _create_r2_client()
    bucket_name = str(ctx.get("r2_bucket_name") or os.environ["R2_BUCKET_NAME"])
    with TemporaryDirectory(prefix="godtier-media-validation-") as temp_dir:
        local_path = Path(temp_dir) / f"source{Path(storage_key).suffix.lower()}"
        await asyncio.to_thread(
            client.download_file,
            bucket_name,
            storage_key,
            str(local_path),
        )
        if local_path.stat().st_size != size_bytes:
            raise ValueError("Uploaded media size changed before validation")
        probe_data = await asyncio.to_thread(probe_media, str(local_path))
        validate_probe_result(probe_data)
    return {
        "status": "validated",
        "user_id": str(parsed_user_id),
        "storage_key": storage_key,
        "content_type": content_type,
        "size_bytes": size_bytes,
    }
