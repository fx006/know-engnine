from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models.enums import (
    FileObjectStatus,
    UploadChunkStatus,
    UploadSessionStatus,
)
from know_engine_py.app.models.upload import (
    FileObjectModel,
    UploadChunkModel,
    UploadSessionModel,
)
from know_engine_py.app.storage.base import FileStorage


@dataclass(slots=True)
class UploadInitResult:
    """上传初始化结果：秒传命中时返回 file_object，否则返回 upload_session。"""

    instant_upload: bool
    file_object: FileObjectModel | None = None
    upload_session: UploadSessionModel | None = None
    uploaded_chunk_indexes: list[int] | None = None


@dataclass(slots=True)
class UploadStatusResult:
    """上传会话状态和已经成功上传的分片索引。"""

    upload_session: UploadSessionModel
    uploaded_chunk_indexes: list[int]


@dataclass(slots=True)
class UploadCompleteResult:
    """上传完成结果：上传会话和生成的完整文件对象。"""

    upload_session: UploadSessionModel
    file_object: FileObjectModel
    uploaded_chunk_indexes: list[int]


class UploadSessionService:
    """分片上传应用服务。

    负责秒传判断、上传会话创建、分片状态记录和断点续传状态查询。
    文件 bytes 的保存由 API 层通过 FileStorage 完成，service 只维护数据库状态。
    """

    def __init__(
        self,
        session: AsyncSession,
        file_storage: FileStorage | None = None,
    ):
        self.session = session
        self.file_storage = file_storage

    async def init_upload(
        self,
        *,
        file_hash: str,
        file_name: str,
        file_size: int,
        chunk_size: int,
        created_by: str,
        content_type: str | None = None,
    ) -> UploadInitResult:
        """初始化上传：命中同 hash 文件则秒传，否则创建 upload session。"""
        normalized_hash = self._normalize_required(file_hash, "file_hash")
        safe_name = self._normalize_file_name(file_name)
        normalized_creator = self._normalize_required(created_by, "created_by")
        self._validate_positive(file_size, "file_size")
        self._validate_positive(chunk_size, "chunk_size")

        existing_file = await self._find_active_file_object(
            file_hash=normalized_hash,
            file_size=file_size,
        )
        if existing_file is not None:
            return UploadInitResult(
                instant_upload=True,
                file_object=existing_file,
                uploaded_chunk_indexes=[],
            )

        upload_session = UploadSessionModel(
            upload_id=uuid4().hex,
            file_hash=normalized_hash,
            file_name=safe_name,
            file_size=file_size,
            chunk_size=chunk_size,
            total_chunks=ceil(file_size / chunk_size),
            uploaded_chunks=0,
            object_name=self._build_final_object_name(
                file_hash=normalized_hash,
                file_name=safe_name,
            ),
            file_object_id=None,
            content_type=(content_type or "").strip() or None,
            status=UploadSessionStatus.UPLOADING.value,
            created_by=normalized_creator,
        )
        self.session.add(upload_session)
        await self.session.flush()

        return UploadInitResult(
            instant_upload=False,
            upload_session=upload_session,
            uploaded_chunk_indexes=[],
        )

    async def mark_chunk_uploaded(
        self,
        *,
        upload_id: str,
        chunk_index: int,
        chunk_size: int,
        object_name: str,
    ) -> UploadChunkModel:
        """记录某个分片已上传；同一分片重复上传时按幂等更新处理。"""
        upload_session = await self._get_upload_session_or_raise(upload_id)
        if upload_session.status != UploadSessionStatus.UPLOADING.value:
            raise ValueError("上传会话状态不是 uploading，不能继续上传分片")
        if chunk_index < 0 or chunk_index >= upload_session.total_chunks:
            raise ValueError("chunk_index 超出上传会话范围")
        self._validate_positive(chunk_size, "chunk_size")
        normalized_object_name = self._normalize_required(object_name, "object_name")

        existing_chunk = await self._get_chunk(upload_id=upload_id, chunk_index=chunk_index)
        if existing_chunk is not None:
            existing_chunk.chunk_size = chunk_size
            existing_chunk.object_name = normalized_object_name
            existing_chunk.status = UploadChunkStatus.UPLOADED.value
            await self.session.flush()
            await self._refresh_uploaded_chunk_count(upload_session)
            return existing_chunk

        upload_chunk = UploadChunkModel(
            upload_id=upload_id,
            chunk_index=chunk_index,
            chunk_size=chunk_size,
            object_name=normalized_object_name,
            status=UploadChunkStatus.UPLOADED.value,
        )
        self.session.add(upload_chunk)
        await self.session.flush()
        await self._refresh_uploaded_chunk_count(upload_session)
        return upload_chunk

    async def get_upload_status(self, upload_id: str) -> UploadStatusResult:
        """查询上传会话状态，返回已上传分片索引用于断点续传。"""
        upload_session = await self._get_upload_session_or_raise(upload_id)
        uploaded_chunk_indexes = await self._list_uploaded_chunk_indexes(upload_id)

        return UploadStatusResult(
            upload_session=upload_session,
            uploaded_chunk_indexes=uploaded_chunk_indexes,
        )

    async def complete_upload(
        self,
        *,
        upload_id: str,
        completed_by: str,
    ) -> UploadCompleteResult:
        """完成分片上传，合并分片并创建完整文件对象。"""
        upload_session = await self._get_upload_session_or_raise(upload_id)
        normalized_user_id = self._normalize_required(completed_by, "completed_by")
        if upload_session.created_by != normalized_user_id:
            raise ValueError("不能完成其他用户的上传会话")

        existing_file = await self._get_completed_file_object(upload_session)
        if existing_file is not None:
            return UploadCompleteResult(
                upload_session=upload_session,
                file_object=existing_file,
                uploaded_chunk_indexes=await self._list_uploaded_chunk_indexes(upload_id),
            )

        if upload_session.status != UploadSessionStatus.UPLOADING.value:
            raise ValueError("上传会话状态不是 uploading，不能完成上传")

        chunk_models = await self._list_uploaded_chunks(upload_id)
        uploaded_chunk_indexes = [chunk.chunk_index for chunk in chunk_models]
        expected_indexes = list(range(upload_session.total_chunks))
        if uploaded_chunk_indexes != expected_indexes:
            raise ValueError("分片未上传完成，不能完成上传")

        if self.file_storage is None:
            raise ValueError("上传合并需要文件存储适配器")

        # 当前 v0.1 第一版采用内存合并，适合验证协议闭环；真实超大文件后续可换成流式合并。
        merged_content = b"".join(
            [
                await self.file_storage.download_bytes(chunk.object_name)
                for chunk in chunk_models
            ]
        )
        file_url = await self.file_storage.upload_bytes(
            object_name=upload_session.object_name,
            content=merged_content,
            content_type=upload_session.content_type or "application/octet-stream",
        )

        file_object = FileObjectModel(
            file_object_id=uuid4().hex,
            file_hash=upload_session.file_hash,
            file_name=upload_session.file_name,
            file_size=upload_session.file_size,
            object_name=upload_session.object_name,
            file_url=file_url,
            content_type=upload_session.content_type,
            status=FileObjectStatus.ACTIVE.value,
            created_by=upload_session.created_by,
        )
        self.session.add(file_object)
        await self.session.flush()

        upload_session.file_object_id = file_object.file_object_id
        upload_session.uploaded_chunks = upload_session.total_chunks
        upload_session.status = UploadSessionStatus.COMPLETED.value
        await self.session.flush()

        return UploadCompleteResult(
            upload_session=upload_session,
            file_object=file_object,
            uploaded_chunk_indexes=uploaded_chunk_indexes,
        )

    async def _find_active_file_object(
        self,
        *,
        file_hash: str,
        file_size: int,
    ) -> FileObjectModel | None:
        result = await self.session.execute(
            select(FileObjectModel)
            .where(FileObjectModel.file_hash == file_hash)
            .where(FileObjectModel.file_size == file_size)
            .where(FileObjectModel.status == FileObjectStatus.ACTIVE.value)
            .order_by(FileObjectModel.id.asc())
        )
        return result.scalars().first()

    async def _get_upload_session_or_raise(
        self,
        upload_id: str,
    ) -> UploadSessionModel:
        normalized_upload_id = self._normalize_required(upload_id, "upload_id")
        result = await self.session.execute(
            select(UploadSessionModel).where(
                UploadSessionModel.upload_id == normalized_upload_id
            )
        )
        upload_session = result.scalar_one_or_none()
        if upload_session is None:
            raise ValueError("上传会话不存在")
        return upload_session

    async def _get_chunk(
        self,
        *,
        upload_id: str,
        chunk_index: int,
    ) -> UploadChunkModel | None:
        result = await self.session.execute(
            select(UploadChunkModel)
            .where(UploadChunkModel.upload_id == upload_id)
            .where(UploadChunkModel.chunk_index == chunk_index)
        )
        return result.scalar_one_or_none()

    async def _list_uploaded_chunks(self, upload_id: str) -> list[UploadChunkModel]:
        result = await self.session.execute(
            select(UploadChunkModel)
            .where(UploadChunkModel.upload_id == upload_id)
            .where(UploadChunkModel.status == UploadChunkStatus.UPLOADED.value)
            .order_by(UploadChunkModel.chunk_index.asc())
        )
        return list(result.scalars().all())

    async def _get_completed_file_object(
        self,
        upload_session: UploadSessionModel,
    ) -> FileObjectModel | None:
        if not upload_session.file_object_id:
            return None

        result = await self.session.execute(
            select(FileObjectModel).where(
                FileObjectModel.file_object_id == upload_session.file_object_id
            )
        )
        return result.scalar_one_or_none()

    async def _list_uploaded_chunk_indexes(self, upload_id: str) -> list[int]:
        result = await self.session.execute(
            select(UploadChunkModel.chunk_index)
            .where(UploadChunkModel.upload_id == upload_id)
            .where(UploadChunkModel.status == UploadChunkStatus.UPLOADED.value)
            .order_by(UploadChunkModel.chunk_index.asc())
        )
        return [int(value) for value in result.scalars().all()]

    async def _refresh_uploaded_chunk_count(
        self,
        upload_session: UploadSessionModel,
    ) -> None:
        result = await self.session.execute(
            select(func.count())
            .select_from(UploadChunkModel)
            .where(UploadChunkModel.upload_id == upload_session.upload_id)
            .where(UploadChunkModel.status == UploadChunkStatus.UPLOADED.value)
        )
        upload_session.uploaded_chunks = int(result.scalar_one())
        await self.session.flush()

    @staticmethod
    def _build_final_object_name(*, file_hash: str, file_name: str) -> str:
        return f"uploads/{file_hash}/{file_name}"

    @staticmethod
    def _normalize_required(value: str, field_name: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} 不能为空")
        return normalized

    @staticmethod
    def _normalize_file_name(file_name: str) -> str:
        safe_name = Path((file_name or "").strip()).name
        if not safe_name:
            raise ValueError("file_name 不能为空")
        return safe_name

    @staticmethod
    def _validate_positive(value: int, field_name: str) -> None:
        if value <= 0:
            raise ValueError(f"{field_name} 必须大于 0")
