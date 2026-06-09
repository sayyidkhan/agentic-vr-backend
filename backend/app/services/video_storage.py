from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

import boto3
from fastapi import HTTPException, UploadFile

from app.config import Settings


@dataclass
class StoredVideo:
    storage_backend: str
    storage_key: str
    playback_url: str
    content_type: str | None
    file_size_bytes: int | None


class VideoStorageService:
    allowed_extensions = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def store_upload(self, upload: UploadFile, *, video_id: str) -> StoredVideo:
        if not upload.filename:
            raise HTTPException(status_code=400, detail="Uploaded file must include a filename")

        suffix = Path(upload.filename).suffix.lower()
        if suffix and suffix not in self.allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Unsupported video file extension: {suffix}")

        content_type = upload.content_type or self._content_type_for_suffix(suffix)
        file_size_bytes = self._get_file_size(upload)
        storage_key = self._build_storage_key(video_id=video_id, suffix=suffix)

        if self.settings.media_storage_backend == "s3":
            self._store_s3(upload=upload, storage_key=storage_key, content_type=content_type)
            playback_url = self._s3_playback_url(storage_key)
            return StoredVideo(
                storage_backend="s3",
                storage_key=storage_key,
                playback_url=playback_url,
                content_type=content_type,
                file_size_bytes=file_size_bytes,
            )

        self._store_local(upload=upload, storage_key=storage_key)
        playback_url = self._local_playback_url(storage_key)
        return StoredVideo(
            storage_backend="local",
            storage_key=storage_key,
            playback_url=playback_url,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
        )

    def _store_local(self, *, upload: UploadFile, storage_key: str) -> None:
        target_path = Path(self.settings.media_local_dir) / storage_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        upload.file.seek(0)
        with target_path.open("wb") as destination:
            shutil.copyfileobj(upload.file, destination)

    def _store_s3(self, *, upload: UploadFile, storage_key: str, content_type: str | None) -> None:
        bucket = self.settings.s3_video_bucket
        if not bucket:
            raise HTTPException(status_code=500, detail="S3_VIDEO_BUCKET must be configured for S3 media storage")

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        upload.file.seek(0)
        boto3.client("s3", region_name=self.settings.aws_region).upload_fileobj(
            upload.file,
            bucket,
            storage_key,
            ExtraArgs=extra_args or None,
        )

    def _build_storage_key(self, *, video_id: str, suffix: str) -> str:
        prefix = self.settings.media_storage_prefix.strip("/")
        filename = f"{video_id}{suffix or '.mp4'}"
        return f"{prefix}/{filename}" if prefix else filename

    @staticmethod
    def _get_file_size(upload: UploadFile) -> int | None:
        try:
            upload.file.seek(0, 2)
            size = upload.file.tell()
            upload.file.seek(0)
            return size
        except OSError:
            upload.file.seek(0)
            return None

    def _local_playback_url(self, storage_key: str) -> str:
        base_path = self.settings.media_public_path.rstrip("/")
        return f"{base_path}/{storage_key}"

    def _s3_playback_url(self, storage_key: str) -> str:
        if self.settings.media_cdn_base_url:
            return f"{self.settings.media_cdn_base_url.rstrip('/')}/{storage_key}"

        bucket = self.settings.s3_video_bucket
        if not bucket:
            raise HTTPException(status_code=500, detail="S3_VIDEO_BUCKET must be configured for S3 playback URLs")
        return f"https://{bucket}.s3.{self.settings.aws_region}.amazonaws.com/{storage_key}"

    @staticmethod
    def _content_type_for_suffix(suffix: str) -> str:
        return {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".m4v": "video/x-m4v",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
        }.get(suffix, "application/octet-stream")
