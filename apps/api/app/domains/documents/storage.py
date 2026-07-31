from __future__ import annotations

import hashlib
import hmac
import io
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.config import settings


class StorageBackend(ABC):
    @abstractmethod
    async def upload(self, file_data: bytes, storage_key: str, content_type: str) -> None:
        ...

    @abstractmethod
    async def download(self, storage_key: str) -> bytes:
        ...

    @abstractmethod
    async def delete(self, storage_key: str) -> None:
        ...

    @abstractmethod
    async def exists(self, storage_key: str) -> bool:
        ...

    @abstractmethod
    async def get_signed_url(self, storage_key: str, expires_in: int = 3600) -> str:
        ...


class LocalStorageBackend(StorageBackend):
    def __init__(self, root: str = "storage/documents") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_key: str) -> Path:
        full_path = self.root / storage_key
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(self.root.resolve())):
            raise ValueError("Invalid storage key")
        return full_path

    async def upload(self, file_data: bytes, storage_key: str, content_type: str) -> None:
        path = self._resolve(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_data)

    async def download(self, storage_key: str) -> bytes:
        return self._resolve(storage_key).read_bytes()

    async def delete(self, storage_key: str) -> None:
        path = self._resolve(storage_key)
        if path.exists():
            path.unlink()

    async def exists(self, storage_key: str) -> bool:
        return self._resolve(storage_key).exists()

    async def get_signed_url(self, storage_key: str, expires_in: int = 3600) -> str:
        expiry = int(time.time()) + expires_in
        secret = settings.document_storage_secret.get_secret_value().encode()
        message = f"{storage_key}:{expiry}".encode()
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return f"/api/documents/download/{storage_key}?expires={expiry}&sig={signature}"


class S3StorageBackend(StorageBackend):
    def __init__(
        self,
        bucket: str,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: str = "us-east-1",
        use_ssl: bool = True,
    ) -> None:
        import boto3
        from botocore.config import Config

        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        config = Config(signature_version="s3v4")
        self.client = session.client(
            "s3",
            endpoint_url=endpoint,
            config=config,
            use_ssl=use_ssl,
        )
        self.bucket = bucket

    async def upload(self, file_data: bytes, storage_key: str, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=storage_key,
            Body=file_data,
            ContentType=content_type,
        )

    async def download(self, storage_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=storage_key)
        return response["Body"].read()

    async def delete(self, storage_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=storage_key)

    async def exists(self, storage_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception:
            return False

    async def get_signed_url(self, storage_key: str, expires_in: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": storage_key},
            ExpiresIn=expires_in,
        )


def get_storage_backend() -> StorageBackend:
    if settings.storage_backend == "s3":
        return S3StorageBackend(
            bucket=settings.s3_bucket_name or "documents",
            endpoint=settings.s3_endpoint,
            access_key=settings.s3_access_key_id,
            secret_key=settings.s3_secret_access_key.get_secret_value() if settings.s3_secret_access_key else None,
            region=settings.s3_region,
            use_ssl=settings.s3_use_ssl,
        )
    return LocalStorageBackend(root=settings.storage_root)
