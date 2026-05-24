from __future__ import annotations

from datetime import datetime,timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from know_engine_py.app.models.document import KnowledgeDocumentModel
from know_engine_py.app.models.enums import DocumentStatus

class DocumentConversionCompensationService:
    """
    处理文档格式转换延迟补偿的服务。
    扫描长时间停留在 UPLOADED 的文档，后续由 Celery task 重新触发 MinerU 转换。
    这里只负责“找候选文档”和“记录补偿结果”，不直接调用外部服务。
    """
    RETRY_COUNT_KEY = "conversionRetryCount"
    LAST_RETRY_TIME_KEY = "lastConversionRetryTime"
    LAST_SUCCESS_KEY = "lastConversionSuccess"
    LAST_ERROR_KEY = "lastConversionError"

    def __init__(self,session: AsyncSession):
        self.session = session

    async def list_candidate_document_ids(
            self,
            *,
            limit:int = 50,
            max_retry_count:int = 5,
            min_age_minutes:int = 5,)->list[int]:
        """查询需要重新触发文档转换的文档 ID"""
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        if max_retry_count <= 0:
            raise ValueError("max_retry_count 必须大于 0")
        if min_age_minutes < 0:
            raise ValueError("min_age_minutes 不能小于 0")

        stmt = (
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.status == DocumentStatus.UPLOADED.value)
            .where(KnowledgeDocumentModel.doc_url.is_not(None))
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
            if not self._has_source_file(document):
                continue

            if self._get_retry_count(document) >= max_retry_count:
                continue

            candidate_ids.append(document.doc_id)
            if len(candidate_ids) >= limit:
                break

        return candidate_ids

    async def record_conversion_result(
            self,
            document_id: int,
            *,
            success: bool,
            error_message: str | None = None,
    ) -> KnowledgeDocumentModel:
        """记录一次转换补偿执行结果。"""
        document = await self._get_document_or_raise(document_id)

        extension = dict(document.extension or {})
        retry_count = self._get_retry_count(document) + 1

        extension[self.RETRY_COUNT_KEY] = retry_count
        extension[self.LAST_RETRY_TIME_KEY] = datetime.now().isoformat(timespec="seconds")
        extension[self.LAST_SUCCESS_KEY] = success

        if error_message:
            # 错误信息只保留摘要，避免把外部服务长报文塞进 JSON 字段。
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

    def _has_source_file(self, document: KnowledgeDocumentModel) -> bool:
        if not document.doc_url or not document.doc_url.strip():
            return False

        extension = document.extension or {}
        source_file_name = extension.get("source_file_name")
        return isinstance(source_file_name, str) and bool(source_file_name.strip())

    def _get_retry_count(self, document: KnowledgeDocumentModel) -> int:
        extension = document.extension or {}
        value = extension.get(self.RETRY_COUNT_KEY, 0)

        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

