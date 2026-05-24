from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from know_engine_py.app.models.document import KnowledgeDocumentModel
from know_engine_py.app.models.enums import DocumentStatus


class DocumentIndexingCompensationService:
    """文档索引补偿扫描服务。

    对齐 Java DocumentCompensationJob 的向量化补偿语义：
    扫描 CHUNKED 状态文档，后续由 Celery task 重新触发索引写入。
    """

    RETRY_COUNT_KEY = "indexingRetryCount"
    LEGACY_RETRY_COUNT_KEY = "retryCount"
    LAST_RETRY_TIME_KEY = "lastIndexingRetryTime"
    LAST_SUCCESS_KEY = "lastIndexingSuccess"
    LAST_ERROR_KEY = "lastIndexingError"

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_candidate_document_ids(
        self,
        *,
        limit: int = 50,
        max_retry_count: int = 5,
        min_age_minutes: int = 5,
    ) -> list[int]:
        """查询需要重新触发索引写入的文档 ID。

        min_age_minutes 用来避免刚进入 CHUNKED 的文档被补偿任务重复处理。
        """
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        if max_retry_count <= 0:
            raise ValueError("max_retry_count 必须大于 0")
        if min_age_minutes < 0:
            raise ValueError("min_age_minutes 不能小于 0")

        stmt = (
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.status == DocumentStatus.CHUNKED.value)
            .order_by(
                KnowledgeDocumentModel.updated_at.asc(),
                KnowledgeDocumentModel.doc_id.asc(),
            )
            .limit(limit * 3)
        )

        if min_age_minutes > 0:
            threshold_time = datetime.now() - timedelta(minutes=min_age_minutes)
            stmt = stmt.where(KnowledgeDocumentModel.updated_at <= threshold_time)

        result = await self.session.execute(stmt)
        documents = list(result.scalars().all())

        candidate_ids: list[int] = []
        for document in documents:
            if self._get_retry_count(document) >= max_retry_count:
                continue

            candidate_ids.append(document.doc_id)
            if len(candidate_ids) >= limit:
                break

        return candidate_ids

    async def record_indexing_result(
        self,
        document_id: int,
        *,
        success: bool,
        error_message: str | None = None,
    ) -> KnowledgeDocumentModel:
        """记录一次索引补偿执行结果。

        不管成功还是失败都增加重试次数，避免失败文档无限重试。
        """
        document = await self._get_document_or_raise(document_id)

        extension = dict(document.extension or {})
        retry_count = self._get_retry_count(document) + 1

        extension[self.RETRY_COUNT_KEY] = retry_count
        extension[self.LAST_RETRY_TIME_KEY] = datetime.now().isoformat(timespec="seconds")
        extension[self.LAST_SUCCESS_KEY] = success

        if error_message:
            extension[self.LAST_ERROR_KEY] = error_message[:500]
        else:
            extension.pop(self.LAST_ERROR_KEY, None)

        document.extension = extension
        flag_modified(document, "extension")
        await self.session.flush()
        return document

    async def _get_document_or_raise(
        self,
        document_id: int,
    ) -> KnowledgeDocumentModel:
        result = await self.session.execute(
            select(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.doc_id == document_id
            )
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise ValueError(f"文档不存在：{document_id}")
        return document

    def _get_retry_count(self, document: KnowledgeDocumentModel) -> int:
        extension = document.extension or {}

        value = extension.get(self.RETRY_COUNT_KEY)
        if value is None:
            value = extension.get(self.LEGACY_RETRY_COUNT_KEY, 0)

        try:
            return int(value)
        except (TypeError, ValueError):
            return 0