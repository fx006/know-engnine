from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentTaskResponse(BaseModel):
    """文档 ETL 任务响应模型，给文档详情页展示处理进度。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    task_id: str = Field(alias="taskId")
    document_id: int = Field(alias="documentId")
    task_type: str = Field(alias="taskType")
    status: str
    celery_task_id: str | None = Field(default=None, alias="celeryTaskId")
    current_attempt: int = Field(alias="currentAttempt")
    max_attempts: int = Field(alias="maxAttempts")
    last_error: str | None = Field(default=None, alias="lastError")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    next_retry_at: datetime | None = Field(default=None, alias="nextRetryAt")
    task_metadata: dict[str, Any] | None = Field(default=None, alias="taskMetadata")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class TaskAttemptResponse(BaseModel):
    """文档 ETL 任务执行尝试响应模型，用于展开查看 worker 执行历史。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    task_id: str = Field(alias="taskId")
    attempt_no: int = Field(alias="attemptNo")
    status: str
    celery_task_id: str | None = Field(default=None, alias="celeryTaskId")
    error_message: str | None = Field(default=None, alias="errorMessage")
    result_payload: dict[str, Any] | None = Field(default=None, alias="resultPayload")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    attempt_metadata: dict[str, Any] | None = Field(
        default=None,
        alias="attemptMetadata",
    )
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
