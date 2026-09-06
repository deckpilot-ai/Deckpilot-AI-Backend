"""Object storage service supporting Cloudflare R2 (S3-compatible) and local fallback."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from app.core.config import settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class StorageService:
    def __init__(self) -> None:
        self.bucket = settings.r2_bucket
        self.use_r2 = bool(
            settings.r2_endpoint_url
            and settings.r2_access_key_id
            and settings.r2_secret_access_key
        )

        self.s3_client: S3Client | None
        if self.use_r2:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                config=Config(signature_version="s3v4"),
                region_name="auto",
            )
        else:
            # Fallback for local development when R2 is not configured
            self.local_storage_dir = Path(settings.local_storage_dir)
            self.local_storage_dir.mkdir(parents=True, exist_ok=True)
            self.s3_client = None

    def _local_path(self, key: str) -> Path:
        root = self.local_storage_dir.resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Storage key resolves outside the configured storage directory")
        return path

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Store bytes in R2 or local storage and return storage key."""
        if self.use_r2 and self.s3_client:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        else:
            file_path = self._local_path(key)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(data)
        return key

    def get_bytes(self, key: str) -> bytes:
        """Retrieve bytes from R2 or local storage."""
        if self.use_r2 and self.s3_client:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        else:
            file_path = self._local_path(key)
            if not file_path.exists():
                raise FileNotFoundError(f"Storage key not found: {key}")
            return file_path.read_bytes()

    def delete_object(self, key: str) -> None:
        """Delete an object from R2 or local storage."""
        if self.use_r2 and self.s3_client:
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
        else:
            file_path = self._local_path(key)
            if file_path.exists():
                file_path.unlink()

    def generate_presigned_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned download URL for an object."""
        if self.use_r2 and self.s3_client:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        return f"/api/v1/storage/{key}"


storage_service = StorageService()
