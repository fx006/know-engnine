from __future__ import annotations

import asyncio
from io import BytesIO
from urllib.parse import urlparse

from minio import Minio

from know_engine_py.app.core.settings import Settings
from know_engine_py.app.storage.base import FileStorage


class MinioFileStorage(FileStorage):
    """MinIO 文件存储适配器。

    对齐 Java FileStorageService：上传、下载、删除文件。
    Python 版统一把 DB 中保存的文件定位符写成 s3://bucket/object。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        client: Minio | None = None,
    ):
        self.settings = settings
        self.bucket = settings.minio_bucket
        self.client = client or self._create_client(settings)

    async def upload_bytes(
        self,
        *,
        object_name: str,
        content: bytes,
        content_type: str,
    ) -> str:
        """上传 bytes 到 MinIO，并返回 s3://bucket/object URL。"""
        safe_object_name = self._normalize_object_name(object_name)

        # MinIO Python SDK 是同步客户端；在 async API 中放到线程池，避免阻塞事件循环。
        await asyncio.to_thread(self._ensure_bucket)
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            safe_object_name,
            BytesIO(content),
            len(content),
            content_type=content_type,
        )

        return self._build_storage_url(safe_object_name)

    async def download_bytes(self, object_name: str) -> bytes:
        """从 MinIO 下载文件内容。"""
        safe_object_name = self._normalize_object_name(object_name)

        response = await asyncio.to_thread(
            self.client.get_object,
            self.bucket,
            safe_object_name,
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def delete(self, object_name: str) -> None:
        """从 MinIO 删除文件。"""
        safe_object_name = self._normalize_object_name(object_name)

        await asyncio.to_thread(
            self.client.remove_object,
            self.bucket,
            safe_object_name,
        )

    def extract_object_name(self, file_url: str) -> str:
        """从 s3://bucket/object 或 http://endpoint/bucket/object 中提取 object。"""
        if not file_url:
            raise ValueError("文件 URL 不能为空")

        # DB 推荐保存 s3://bucket/object；兼容 Java 版 http://endpoint/bucket/object。
        parsed = urlparse(file_url)

        if parsed.scheme == "s3":
            if parsed.netloc != self.bucket:
                raise ValueError(f"文件 URL bucket 不匹配：{file_url}")
            return self._normalize_object_name(parsed.path)

        path = parsed.path.lstrip("/") if parsed.scheme else file_url.lstrip("/")
        bucket_prefix = f"{self.bucket}/"

        if path.startswith(bucket_prefix):
            return self._normalize_object_name(path[len(bucket_prefix):])

        return self._normalize_object_name(path)

    def _create_client(self, settings: Settings) -> Minio:
        endpoint = settings.minio_endpoint.strip()
        if not endpoint:
            raise ValueError("MINIO_ENDPOINT 未配置")
        if not settings.minio_access_key.strip():
            raise ValueError("MINIO_ACCESS_KEY 未配置")
        if not settings.minio_secret_key.strip():
            raise ValueError("MINIO_SECRET_KEY 未配置")

        secure = settings.minio_secure
        if endpoint.startswith("https://"):
            endpoint = endpoint.removeprefix("https://")
            secure = True
        elif endpoint.startswith("http://"):
            endpoint = endpoint.removeprefix("http://")

        return Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=secure,
        )

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def _build_storage_url(self, object_name: str) -> str:
        return f"s3://{self.bucket}/{object_name}"

    def _normalize_object_name(self, object_name: str) -> str:
        normalized = object_name.lstrip("/")
        if not normalized:
            raise ValueError("object_name 不能为空")
        return normalized
