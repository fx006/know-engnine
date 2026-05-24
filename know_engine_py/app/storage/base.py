from __future__ import annotations

from typing import Protocol


class FileStorage(Protocol):
    """文件存储协议。

    业务层只依赖这个协议，不直接依赖 MinIO SDK。
    """

    async def upload_bytes(
        self,
        *,
        object_name: str,
        content: bytes,
        content_type: str,
    ) -> str:
        """上传 bytes，返回可持久化到 DB 的文件 URL。"""
        ...

    async def download_bytes(self, object_name: str) -> bytes:
        """按 object name 下载文件内容。"""
        ...

    async def delete(self, object_name: str) -> None:
        """删除文件。"""
        ...

    def extract_object_name(self, file_url: str) -> str:
        """从 DB 中保存的 URL 反解 object name。"""
        ...