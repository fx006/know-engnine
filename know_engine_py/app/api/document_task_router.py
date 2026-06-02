from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.api.dependencies.auth import get_current_user
from know_engine_py.app.db.session import get_db
from know_engine_py.app.models.auth import UserModel
from know_engine_py.app.models.document import KnowledgeDocumentModel
from know_engine_py.app.models.document_task import DocumentTaskModel
from know_engine_py.app.models.enums import DocumentTaskType
from know_engine_py.app.schemas.document_task import (
    DocumentTaskResponse,
    TaskAttemptResponse,
)
from know_engine_py.app.services.access_control_service import AccessControlService
from know_engine_py.app.services.document_task_service import DocumentTaskService
from know_engine_py.app.tasks.document_tasks import (
    enqueue_document_conversion,
    enqueue_document_indexing,
)

router = APIRouter(tags=["document-tasks"])


@router.get(
    "/documents/{document_id}/tasks",
    response_model=list[DocumentTaskResponse],
)
async def list_document_tasks(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """查询文档 ETL 任务列表，用于文档详情页展示处理进度。"""
    document = await _get_document_or_404(db, document_id)
    await _ensure_document_access(db, document, current_user)

    service = DocumentTaskService(db)
    return await service.list_document_tasks(document_id)


@router.get(
    "/document-tasks/{task_id}/attempts",
    response_model=list[TaskAttemptResponse],
)
async def list_task_attempts(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """查询任务执行 attempts，用于展开查看 worker 每次执行历史。"""
    service = DocumentTaskService(db)

    try:
        task = await service.get_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    document = await _get_document_or_404(db, task.document_id)
    await _ensure_document_access(db, document, current_user)
    return await service.list_task_attempts(task_id)


@router.post(
    "/document-tasks/{task_id}/retry",
    response_model=DocumentTaskResponse,
)
async def retry_document_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """手动重试失败的文档 ETL 任务，并重新投递对应 Celery task。"""
    service = DocumentTaskService(db)

    try:
        task = await service.get_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    document = await _get_document_or_404(db, task.document_id)
    await _ensure_document_access(db, document, current_user)

    if task.task_type == DocumentTaskType.SPLIT.value:
        raise HTTPException(status_code=400, detail="split 任务暂不支持自动重试")
    if task.task_type not in {
        DocumentTaskType.CONVERT.value,
        DocumentTaskType.INDEX.value,
    }:
        raise HTTPException(status_code=400, detail="不支持的任务类型")

    try:
        retried_task = await service.retry_task(task_id)
        await db.flush()

        celery_task_id = _enqueue_retry_task(retried_task)
        queued_task = await service.mark_task_queued(
            retried_task.task_id,
            celery_task_id=celery_task_id,
        )
        await db.commit()
        await db.refresh(queued_task)
        return queued_task
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _get_document_or_404(
    db: AsyncSession,
    document_id: int,
) -> KnowledgeDocumentModel:
    result = await db.execute(
        select(KnowledgeDocumentModel).where(
            KnowledgeDocumentModel.doc_id == document_id
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document


async def _ensure_document_access(
    db: AsyncSession,
    document: KnowledgeDocumentModel,
    current_user: UserModel,
) -> None:
    """按文档所属 group 校验任务可见性，避免跨知识库查看 ETL 进度。"""
    if not document.group_id:
        raise HTTPException(status_code=403, detail="文档缺少群组归属")

    access_service = AccessControlService(db)
    if not await access_service.is_group_member(
        group_id=document.group_id,
        user_id=current_user.user_id,
    ):
        raise HTTPException(status_code=403, detail="用户不是文档所属群组成员")


def _enqueue_retry_task(task: DocumentTaskModel) -> str:
    """按任务类型重新投递 Celery task。"""
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
