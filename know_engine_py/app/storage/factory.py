from __future__ import annotations

from know_engine_py.app.core.settings import Settings, get_settings
from know_engine_py.app.storage.base import FileStorage
from know_engine_py.app.storage.minio_storage import MinioFileStorage


def create_file_storage(settings: Settings | None = None) -> FileStorage:
    """创建文件存储适配器。

    当前只有 MinIO 实现；保留 factory 是为了后续可替换本地存储、S3 或测试 fake。
    """
    current_settings = settings or get_settings()
    return MinioFileStorage(settings=current_settings)