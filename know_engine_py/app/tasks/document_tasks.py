from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.vectorstores import VectorStore

from know_engine_py.app.core.settings import Settings, get_settings
from know_engine_py.app.db.session import get_session_maker
from know_engine_py.app.rag.indexes.elasticsearch_bm25 import (
    ElasticsearchBM25IndexFactory,
)
from know_engine_py.app.rag.vectorstores.milvus import MilvusVectorStoreFactory
from know_engine_py.app.services.document_indexing_service import (
    DocumentIndexingService,
)
from know_engine_py.app.services.document_indexing_compensation_service import (
    DocumentIndexingCompensationService,
)
from know_engine_py.app.tasks.celery_app import celery_app

from know_engine_py.app.rag.parsers.mineru_client import MinerUClient
from know_engine_py.app.services.document_conversion_service import (
    DocumentConversionService,
)
from know_engine_py.app.storage.factory import create_file_storage
from know_engine_py.app.services.document_conversion_compensation_service import (
    DocumentConversionCompensationService,
)


@celery_app.task(name="know_engine.document.index")
def index_document_task(document_id: int) -> dict[str, Any]:
    """Celery 文档索引任务入口。

    Celery task 本身是同步函数；真正的 DB 和索引写入逻辑放到 async helper 中执行。
    """
    return asyncio.run(index_document_async(document_id))


async def index_document_async(document_id: int) -> dict[str, Any]:
    """执行文档索引写入。

    当前要求 Milvus 可用；Elasticsearch BM25 如果配置了则一起写入，
    未配置时只写向量索引。
    """
    if document_id <= 0:
        raise ValueError("document_id 必须大于 0")

    settings = get_settings()
    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            vector_store = _create_vector_store(settings)
            keyword_store = _create_keyword_store(settings)

            service = DocumentIndexingService(
                session=session,
                vector_store=vector_store,
                keyword_store=keyword_store,
            )
            success = await service.index_document(document_id)

            await session.commit()

            return {
                "document_id": document_id,
                "success": success,
            }
        except Exception:
            await session.rollback()
            raise


@celery_app.task(name="know_engine.document.index_compensation")
def compensate_document_indexing_task(
    limit: int = 50,
    max_retry_count: int = 5,
    min_age_minutes: int = 5,
) -> dict[str, Any]:
    """Celery 文档索引补偿任务。

    扫描长时间停留在 CHUNKED 的文档，重新触发索引写入。
    """
    return asyncio.run(
        compensate_document_indexing_async(
            limit=limit,
            max_retry_count=max_retry_count,
            min_age_minutes=min_age_minutes,
        )
    )


async def compensate_document_indexing_async(
    *,
    limit: int = 50,
    max_retry_count: int = 5,
    min_age_minutes: int = 5,
) -> dict[str, Any]:
    """执行一轮文档索引补偿。"""
    document_ids = await _list_indexing_compensation_candidates(
        limit=limit,
        max_retry_count=max_retry_count,
        min_age_minutes=min_age_minutes,
    )

    results: list[dict[str, Any]] = []

    for document_id in document_ids:
        try:
            index_result = await index_document_async(document_id)
            success = bool(index_result.get("success"))

            await _record_indexing_compensation_result(
                document_id,
                success=success,
            )

            results.append(
                {
                    "document_id": document_id,
                    "success": success,
                    "error": None,
                }
            )
        except Exception as exc:
            error_message = str(exc)

            await _record_indexing_compensation_result(
                document_id,
                success=False,
                error_message=error_message,
            )

            results.append(
                {
                    "document_id": document_id,
                    "success": False,
                    "error": error_message,
                }
            )

    success_count = sum(1 for item in results if item["success"])
    failure_count = len(results) - success_count

    return {
        "candidate_count": len(document_ids),
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results,
    }


@celery_app.task(name="know_engine.document.convert")
def convert_document_task(document_id: int) -> dict[str, Any]:
    """Celery 文档转换任务入口。

    用于处理 PDF/Word 等非直通文件：从对象存储读取原文件，
    调用 MinerU 转 Markdown，再更新文档为 CONVERTED。
    """
    return asyncio.run(convert_document_async(document_id))


async def convert_document_async(document_id: int) -> dict[str, Any]:
    """执行文档转换任务。"""
    if document_id <= 0:
        raise ValueError("document_id 必须大于 0")

    settings = get_settings()
    if not settings.mineru_base_url.strip():
        raise ValueError("MinerU 服务地址未配置")

    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            file_storage = create_file_storage(settings)
            mineru_client = MinerUClient(
                base_url=settings.mineru_base_url,
                api_key=settings.mineru_api_key,
            )

            service = DocumentConversionService(
                session=session,
                file_storage=file_storage,
                mineru_client=mineru_client,
            )
            document = await service.convert_document_to_markdown(document_id)

            await session.commit()

            return {
                "document_id": document.doc_id,
                "status": document.status,
                "converted_doc_url": document.converted_doc_url,
            }
        except Exception:
            await session.rollback()
            raise



@celery_app.task(name="know_engine.document.convert_compensation")
def compensate_document_conversion_task(
    limit: int = 50,
    max_retry_count: int = 5,
    min_age_minutes: int = 5,
) -> dict[str, Any]:
    """Celery 文档转换补偿任务。

    扫描长时间停留在 UPLOADED 的非直通文档，重新触发 MinerU 转换。
    """
    return asyncio.run(
        compensate_document_conversion_async(
            limit=limit,
            max_retry_count=max_retry_count,
            min_age_minutes=min_age_minutes,
        )
    )


async def compensate_document_conversion_async(
    *,
    limit: int = 50,
    max_retry_count: int = 5,
    min_age_minutes: int = 5,
) -> dict[str, Any]:
    """执行一轮文档转换补偿。"""
    document_ids = await _list_conversion_compensation_candidates(
        limit=limit,
        max_retry_count=max_retry_count,
        min_age_minutes=min_age_minutes,
    )

    results: list[dict[str, Any]] = []

    for document_id in document_ids:
        try:
            await convert_document_async(document_id)

            await _record_conversion_compensation_result(
                document_id,
                success=True,
            )

            results.append(
                {
                    "document_id": document_id,
                    "success": True,
                    "error": None,
                }
            )
        except Exception as exc:
            error_message = str(exc)

            await _record_conversion_compensation_result(
                document_id,
                success=False,
                error_message=error_message,
            )

            results.append(
                {
                    "document_id": document_id,
                    "success": False,
                    "error": error_message,
                }
            )

    success_count = sum(1 for item in results if item["success"])
    failure_count = len(results) - success_count

    return {
        "candidate_count": len(document_ids),
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results,
    }


def enqueue_document_conversion(document_id: int) -> str:
    """投递文档转换任务，返回 Celery task id。"""
    if document_id <= 0:
        raise ValueError("document_id 必须大于 0")

    async_result = convert_document_task.delay(document_id)
    return str(async_result.id)

def enqueue_document_indexing(document_id: int)->str:
    """投递文档索引任务，返回 Celery task id。"""
    if document_id<=0:
        raise ValueError("document_id 必须大于0")

    async_result = index_document_task.delay(document_id)
    return str(async_result.id)

async def _list_indexing_compensation_candidates(
    *,
    limit: int,
    max_retry_count: int,
    min_age_minutes: int,
) -> list[int]:
    """查询本轮需要补偿索引的文档 ID。"""
    session_maker = get_session_maker()

    async with session_maker() as session:
        service = DocumentIndexingCompensationService(session)
        return await service.list_candidate_document_ids(
            limit=limit,
            max_retry_count=max_retry_count,
            min_age_minutes=min_age_minutes,
        )


async def _record_indexing_compensation_result(
    document_id: int,
    *,
    success: bool,
    error_message: str | None = None,
) -> None:
    """记录单个文档补偿结果。"""
    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            service = DocumentIndexingCompensationService(session)
            await service.record_indexing_result(
                document_id,
                success=success,
                error_message=error_message,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _create_vector_store(settings: Settings) -> VectorStore:
    """创建必需的向量索引写入端。"""
    return MilvusVectorStoreFactory(settings=settings).create()


def _create_keyword_store(settings: Settings) -> VectorStore | None:
    """如果配置了 ES，则创建 BM25 关键词索引写入端。"""
    if not settings.elasticsearch_url.strip():
        return None

    return ElasticsearchBM25IndexFactory(settings=settings).create()

async def _list_conversion_compensation_candidates(
    *,
    limit: int,
    max_retry_count: int,
    min_age_minutes: int,
) -> list[int]:
    """查询本轮需要补偿转换的文档 ID。"""
    session_maker = get_session_maker()

    async with session_maker() as session:
        service = DocumentConversionCompensationService(session)
        return await service.list_candidate_document_ids(
            limit=limit,
            max_retry_count=max_retry_count,
            min_age_minutes=min_age_minutes,
        )


async def _record_conversion_compensation_result(
    document_id: int,
    *,
    success: bool,
    error_message: str | None = None,
) -> None:
    """记录单个文档转换补偿结果。"""
    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            service = DocumentConversionCompensationService(session)
            await service.record_conversion_result(
                document_id,
                success=success,
                error_message=error_message,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise