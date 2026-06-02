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
from know_engine_py.app.models.document_task import DocumentTaskModel
from know_engine_py.app.models.enums import DocumentTaskStatus, DocumentTaskType
from know_engine_py.app.services.document_task_service import DocumentTaskService
from know_engine_py.app.tasks.celery_app import celery_app

from know_engine_py.app.rag.parsers.mineru_client import MinerUClient
from know_engine_py.app.services.document_conversion_service import (
    DocumentConversionService,
)
from know_engine_py.app.storage.factory import create_file_storage
from know_engine_py.app.services.document_conversion_compensation_service import (
    DocumentConversionCompensationService,
)


@celery_app.task(name="know_engine.document.index", bind=True)
def index_document_task(
    self,
    document_id: int,
    document_task_id: str | None = None,
) -> dict[str, Any]:
    """Celery 文档索引任务入口。

    Celery task 本身是同步函数；真正的 DB 和索引写入逻辑放到 async helper 中执行。
    """
    return asyncio.run(
        index_document_async(
            document_id,
            document_task_id=document_task_id,
            celery_task_id=str(self.request.id) if self.request.id else None,
        )
    )


async def index_document_async(
    document_id: int,
    *,
    document_task_id: str | None = None,
    celery_task_id: str | None = None,
) -> dict[str, Any]:
    """执行文档索引写入。

    当前要求 Milvus 可用；Elasticsearch BM25 如果配置了则一起写入，
    未配置时只写向量索引。
    """
    if document_id <= 0:
        raise ValueError("document_id 必须大于 0")

    settings = get_settings()
    session_maker = get_session_maker()

    async with session_maker() as session:
        tracked_task_id: str | None = None
        try:
            tracked_task_id = await _start_document_task_attempt(
                session,
                document_id=document_id,
                task_type=DocumentTaskType.INDEX,
                document_task_id=document_task_id,
                celery_task_id=celery_task_id,
            )
            vector_store = _create_vector_store(settings)
            keyword_store = _create_keyword_store(settings)

            service = DocumentIndexingService(
                session=session,
                vector_store=vector_store,
                keyword_store=keyword_store,
            )
            success = await service.index_document(document_id)

            result = {
                "document_id": document_id,
                "success": success,
                "document_task_id": tracked_task_id,
            }
            await _complete_document_task_attempt(
                session,
                tracked_task_id,
                result=result,
            )
            await session.commit()

            return result
        except Exception as exc:
            await session.rollback()
            await _fail_document_task_attempt(
                session,
                tracked_task_id,
                error_message=str(exc),
            )
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


@celery_app.task(name="know_engine.document.task_compensation")
def compensate_document_tasks_task(
    limit: int = 50,
    min_age_minutes: int = 5,
) -> dict[str, Any]:
    """Celery 文档 ETL 任务台账补偿任务。"""
    return asyncio.run(
        compensate_document_tasks_async(
            limit=limit,
            min_age_minutes=min_age_minutes,
        )
    )


async def compensate_document_tasks_async(
    *,
    limit: int = 50,
    min_age_minutes: int = 5,
) -> dict[str, Any]:
    """执行一轮文档 ETL 任务台账补偿。"""
    if limit <= 0:
        raise ValueError("limit 必须大于 0")
    if min_age_minutes < 0:
        raise ValueError("min_age_minutes 不能小于 0")

    session_maker = get_session_maker()
    results: list[dict[str, Any]] = []

    async with session_maker() as session:
        service = DocumentTaskService(session)
        candidates = await service.list_compensation_candidates(
            limit=limit,
            min_age_minutes=min_age_minutes,
        )

        for candidate in candidates:
            try:
                result = await _compensate_document_task_candidate(
                    service,
                    candidate,
                )
                await session.commit()
            except Exception as exc:
                await session.rollback()
                result = _build_task_compensation_result(
                    candidate,
                    action="failed",
                    error=str(exc),
                )

            results.append(result)

    queued_count = sum(1 for item in results if item["action"] == "queued")
    skipped_count = sum(1 for item in results if item["action"] == "skipped")
    failure_count = sum(1 for item in results if item["action"] == "failed")

    return {
        "candidate_count": len(results),
        "queued_count": queued_count,
        "skipped_count": skipped_count,
        "failure_count": failure_count,
        "results": results,
    }


async def _compensate_document_task_candidate(
    service: DocumentTaskService,
    task: DocumentTaskModel,
) -> dict[str, Any]:
    """补偿单个 document_task，返回统计项。"""
    if task.task_type == DocumentTaskType.SPLIT.value:
        return _build_task_compensation_result(
            task,
            action="skipped",
            error="split 任务暂不支持自动补偿",
        )

    if task.task_type not in {
        DocumentTaskType.CONVERT.value,
        DocumentTaskType.INDEX.value,
    }:
        return _build_task_compensation_result(
            task,
            action="skipped",
            error="不支持的任务类型",
        )

    if task.status == DocumentTaskStatus.RUNNING.value:
        # running 超时说明当前 attempt 很可能已经丢失，先把本次 attempt 标为失败，再进入重试队列。
        await service.fail_task(
            task.task_id,
            error_message="任务运行超时，补偿任务重新投递",
        )
        task = await service.retry_task(task.task_id)
    elif task.status == DocumentTaskStatus.FAILED.value:
        task = await service.retry_task(task.task_id)
    elif task.status != DocumentTaskStatus.PENDING.value:
        return _build_task_compensation_result(
            task,
            action="skipped",
            error=f"任务状态 {task.status} 不需要补偿",
        )

    celery_task_id = _enqueue_document_task(task)
    task = await service.mark_task_queued(
        task.task_id,
        celery_task_id=celery_task_id,
    )

    return _build_task_compensation_result(
        task,
        action="queued",
        celery_task_id=celery_task_id,
    )


def _enqueue_document_task(task: DocumentTaskModel) -> str:
    """按 document_task 类型重新投递 Celery。"""
    if task.task_type == DocumentTaskType.CONVERT.value:
        return enqueue_document_conversion(
            task.document_id,
            document_task_id=task.task_id,
        )
    if task.task_type == DocumentTaskType.INDEX.value:
        return enqueue_document_indexing(
            task.document_id,
            document_task_id=task.task_id,
        )
    raise ValueError("不支持的任务类型")


def _build_task_compensation_result(
    task: DocumentTaskModel,
    *,
    action: str,
    celery_task_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "document_id": task.document_id,
        "task_type": task.task_type,
        "status": task.status,
        "action": action,
        "celery_task_id": celery_task_id or task.celery_task_id,
        "error": error,
    }


@celery_app.task(name="know_engine.document.convert", bind=True)
def convert_document_task(
    self,
    document_id: int,
    document_task_id: str | None = None,
) -> dict[str, Any]:
    """Celery 文档转换任务入口。

    用于处理 PDF/Word 等非直通文件：从对象存储读取原文件，
    调用 MinerU 转 Markdown，再更新文档为 CONVERTED。
    """
    return asyncio.run(
        convert_document_async(
            document_id,
            document_task_id=document_task_id,
            celery_task_id=str(self.request.id) if self.request.id else None,
        )
    )


async def convert_document_async(
    document_id: int,
    *,
    document_task_id: str | None = None,
    celery_task_id: str | None = None,
) -> dict[str, Any]:
    """执行文档转换任务。"""
    if document_id <= 0:
        raise ValueError("document_id 必须大于 0")

    session_maker = get_session_maker()

    async with session_maker() as session:
        tracked_task_id: str | None = None
        try:
            tracked_task_id = await _start_document_task_attempt(
                session,
                document_id=document_id,
                task_type=DocumentTaskType.CONVERT,
                document_task_id=document_task_id,
                celery_task_id=celery_task_id,
            )
            settings = get_settings()
            if not settings.mineru_base_url.strip():
                raise ValueError("MinerU 服务地址未配置")

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

            result = {
                "document_id": document.doc_id,
                "status": document.status,
                "converted_doc_url": document.converted_doc_url,
                "document_task_id": tracked_task_id,
            }
            await _complete_document_task_attempt(
                session,
                tracked_task_id,
                result=result,
            )
            await session.commit()

            return result
        except Exception as exc:
            await session.rollback()
            await _fail_document_task_attempt(
                session,
                tracked_task_id,
                error_message=str(exc),
            )
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


def enqueue_document_conversion(
    document_id: int,
    *,
    document_task_id: str | None = None,
) -> str:
    """投递文档转换任务，返回 Celery task id。"""
    if document_id <= 0:
        raise ValueError("document_id 必须大于 0")

    async_result = convert_document_task.delay(document_id, document_task_id)
    return str(async_result.id)

def enqueue_document_indexing(
    document_id: int,
    *,
    document_task_id: str | None = None,
)->str:
    """投递文档索引任务，返回 Celery task id。"""
    if document_id<=0:
        raise ValueError("document_id 必须大于0")

    async_result = index_document_task.delay(document_id, document_task_id)
    return str(async_result.id)


async def _start_document_task_attempt(
    session,
    *,
    document_id: int,
    task_type: DocumentTaskType,
    document_task_id: str | None,
    celery_task_id: str | None,
) -> str:
    """启动任务台账 attempt。

    如果调用方还没有创建 DocumentTask，则 worker 自动创建一条，保证老入口也能被观测。
    """
    task_service = DocumentTaskService(session)
    if document_task_id:
        tracked_task_id = document_task_id
    else:
        task = await task_service.create_task(
            document_id=document_id,
            task_type=task_type,
            metadata={"source": "worker_autocreated"},
        )
        tracked_task_id = task.task_id

    await task_service.start_task(
        tracked_task_id,
        celery_task_id=celery_task_id,
        metadata={"celery_task_id": celery_task_id} if celery_task_id else None,
    )
    # 先提交 running attempt，避免业务执行失败或 worker 崩溃后完全没有过程记录。
    await session.commit()
    return tracked_task_id


async def _complete_document_task_attempt(
    session,
    task_id: str | None,
    *,
    result: dict[str, Any],
) -> None:
    if not task_id:
        return

    await DocumentTaskService(session).complete_task(task_id, result=result)


async def _fail_document_task_attempt(
    session,
    task_id: str | None,
    *,
    error_message: str,
) -> None:
    if not task_id:
        return

    try:
        await DocumentTaskService(session).fail_task(
            task_id,
            error_message=error_message,
        )
        await session.commit()
    except Exception:
        await session.rollback()

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
