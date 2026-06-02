from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models.document_task import (
    DocumentTaskModel,
    TaskAttemptModel,
)
from know_engine_py.app.models.enums import DocumentTaskStatus, DocumentTaskType


class DocumentTaskService:
    """文档 ETL 任务台账服务。

    负责记录任务生命周期和每次执行 attempt；不直接调用 Celery，也不直接做转换/索引。
    事务边界由调用方控制。
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        max_error_length: int = 1000,
    ):
        self.session = session
        self.max_error_length = max_error_length

    async def create_task(
        self,
        *,
        document_id: int,
        task_type: DocumentTaskType | str,
        max_attempts: int = 3,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentTaskModel:
        """创建待执行任务。"""
        if document_id <= 0:
            raise ValueError("document_id 必须大于 0")
        if max_attempts <= 0:
            raise ValueError("max_attempts 必须大于 0")

        task = DocumentTaskModel(
            task_id=uuid4().hex,
            document_id=document_id,
            task_type=self._task_type_value(task_type),
            status=DocumentTaskStatus.PENDING.value,
            celery_task_id=None,
            current_attempt=0,
            max_attempts=max_attempts,
            last_error=None,
            started_at=None,
            finished_at=None,
            next_retry_at=None,
            task_metadata=dict(metadata or {}),
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def start_task(
        self,
        task_id: str,
        *,
        celery_task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskAttemptModel:
        """将任务置为 running，并创建一条 attempt 记录。"""
        task = await self._get_task_or_raise(task_id)
        if task.status not in {
            DocumentTaskStatus.PENDING.value,
            DocumentTaskStatus.RETRYING.value,
        }:
            raise ValueError(f"任务状态为 {task.status}，不能开始执行")
        if task.current_attempt >= task.max_attempts:
            raise ValueError("任务已达到最大尝试次数")

        now = datetime.now()
        attempt_no = task.current_attempt + 1
        task.status = DocumentTaskStatus.RUNNING.value
        task.current_attempt = attempt_no
        task.celery_task_id = celery_task_id
        task.started_at = now
        task.finished_at = None
        task.last_error = None

        attempt = TaskAttemptModel(
            task_id=task.task_id,
            attempt_no=attempt_no,
            status=DocumentTaskStatus.RUNNING.value,
            celery_task_id=celery_task_id,
            error_message=None,
            result_payload=None,
            started_at=now,
            finished_at=None,
            attempt_metadata=dict(metadata or {}),
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def complete_task(
        self,
        task_id: str,
        *,
        result: dict[str, Any] | None = None,
    ) -> DocumentTaskModel:
        """将当前 running 任务标记为 success。"""
        task = await self._get_task_or_raise(task_id)
        if task.status != DocumentTaskStatus.RUNNING.value:
            raise ValueError(f"任务状态为 {task.status}，不能完成")

        now = datetime.now()
        task.status = DocumentTaskStatus.SUCCESS.value
        task.finished_at = now
        task.last_error = None

        attempt = await self._get_current_attempt_or_raise(task)
        attempt.status = DocumentTaskStatus.SUCCESS.value
        attempt.result_payload = dict(result or {})
        attempt.finished_at = now

        await self.session.flush()
        return task

    async def fail_task(
        self,
        task_id: str,
        *,
        error_message: str,
    ) -> DocumentTaskModel:
        """将当前 running 任务标记为 failed，并记录截断后的错误摘要。"""
        task = await self._get_task_or_raise(task_id)
        if task.status != DocumentTaskStatus.RUNNING.value:
            raise ValueError(f"任务状态为 {task.status}，不能标记失败")

        now = datetime.now()
        safe_error = self._truncate_error(error_message)
        task.status = DocumentTaskStatus.FAILED.value
        task.finished_at = now
        task.last_error = safe_error

        attempt = await self._get_current_attempt_or_raise(task)
        attempt.status = DocumentTaskStatus.FAILED.value
        attempt.error_message = safe_error
        attempt.finished_at = now

        await self.session.flush()
        return task

    async def retry_task(self, task_id: str) -> DocumentTaskModel:
        """将 failed 任务重新置为 pending，等待下一次投递。"""
        task = await self._get_task_or_raise(task_id)
        if task.status != DocumentTaskStatus.FAILED.value:
            raise ValueError(f"任务状态为 {task.status}，不能 retry")
        if task.current_attempt >= task.max_attempts:
            raise ValueError("任务已达到最大尝试次数")

        task.status = DocumentTaskStatus.PENDING.value
        task.celery_task_id = None
        task.started_at = None
        task.finished_at = None
        await self.session.flush()
        return task

    async def mark_task_queued(
        self,
        task_id: str,
        *,
        celery_task_id: str,
    ) -> DocumentTaskModel:
        """记录任务重新投递后的 Celery task id。"""
        normalized_celery_task_id = (celery_task_id or "").strip()
        if not normalized_celery_task_id:
            raise ValueError("celery_task_id 不能为空")

        task = await self._get_task_or_raise(task_id)
        task.celery_task_id = normalized_celery_task_id
        await self.session.flush()
        return task

    async def get_task(self, task_id: str) -> DocumentTaskModel:
        """按 task_id 查询任务，不存在时抛出业务异常。"""
        return await self._get_task_or_raise(task_id)

    async def list_document_tasks(
        self,
        document_id: int,
    ) -> list[DocumentTaskModel]:
        """查询某个文档的全部 ETL 任务。"""
        if document_id <= 0:
            raise ValueError("document_id 必须大于 0")

        result = await self.session.execute(
            select(DocumentTaskModel)
            .where(DocumentTaskModel.document_id == document_id)
            .order_by(DocumentTaskModel.id.desc())
        )
        return list(result.scalars().all())

    async def list_task_attempts(
        self,
        task_id: str,
    ) -> list[TaskAttemptModel]:
        """查询某个任务的全部执行尝试记录。"""
        task = await self._get_task_or_raise(task_id)
        result = await self.session.execute(
            select(TaskAttemptModel)
            .where(TaskAttemptModel.task_id == task.task_id)
            .order_by(TaskAttemptModel.attempt_no.asc())
        )
        return list(result.scalars().all())

    async def list_compensation_candidates(
        self,
        *,
        limit: int = 50,
        min_age_minutes: int = 5,
    ) -> list[DocumentTaskModel]:
        """扫描需要补偿的任务。

        规则：
        1. pending 超过阈值：可能投递失败或队列消息丢失。
        2. running 超过阈值：可能 worker 崩溃或任务卡死。
        3. failed 且未达最大尝试次数：可以重新投递。
        """
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        if min_age_minutes < 0:
            raise ValueError("min_age_minutes 不能小于 0")

        # BaseEntity 的 server_default=func.now() 在 SQLite/PostgreSQL 常以 UTC 写入；
        # 这里使用 UTC naive 时间，避免本地时区把刚创建任务误判为超时。
        threshold_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            minutes=min_age_minutes
        )
        retryable_filter = DocumentTaskModel.current_attempt < DocumentTaskModel.max_attempts

        result = await self.session.execute(
            select(DocumentTaskModel)
            .where(retryable_filter)
            .where(
                or_(
                    and_(
                        DocumentTaskModel.status == DocumentTaskStatus.PENDING.value,
                        DocumentTaskModel.updated_at <= threshold_time,
                    ),
                    and_(
                        DocumentTaskModel.status == DocumentTaskStatus.RUNNING.value,
                        DocumentTaskModel.updated_at <= threshold_time,
                    ),
                    DocumentTaskModel.status == DocumentTaskStatus.FAILED.value,
                )
            )
            .order_by(DocumentTaskModel.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_task_or_raise(self, task_id: str) -> DocumentTaskModel:
        normalized_task_id = (task_id or "").strip()
        if not normalized_task_id:
            raise ValueError("task_id 不能为空")

        result = await self.session.execute(
            select(DocumentTaskModel).where(
                DocumentTaskModel.task_id == normalized_task_id
            )
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise ValueError(f"任务不存在：{normalized_task_id}")
        return task

    async def _get_current_attempt_or_raise(
        self,
        task: DocumentTaskModel,
    ) -> TaskAttemptModel:
        result = await self.session.execute(
            select(TaskAttemptModel)
            .where(TaskAttemptModel.task_id == task.task_id)
            .where(TaskAttemptModel.attempt_no == task.current_attempt)
        )
        attempt = result.scalar_one_or_none()
        if attempt is None:
            raise ValueError("当前任务执行记录不存在")
        return attempt

    def _truncate_error(self, error_message: str | None) -> str:
        safe_error = (error_message or "").strip()
        if not safe_error:
            safe_error = "未知错误"
        return safe_error[: self.max_error_length]

    @staticmethod
    def _task_type_value(task_type: DocumentTaskType | str) -> str:
        if isinstance(task_type, DocumentTaskType):
            return task_type.value

        value = (task_type or "").strip()
        allowed_values = {item.value for item in DocumentTaskType}
        if value not in allowed_values:
            raise ValueError(f"不支持的任务类型：{value}")
        return value
