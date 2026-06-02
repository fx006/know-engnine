from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from know_engine_py.app.models.base import Base, BaseEntity


class DocumentTaskModel(Base, BaseEntity):
    """文档 ETL 任务表：记录转换、切分、索引等后台任务的当前状态。"""

    __tablename__ = "document_task"
    __table_args__ = (
        UniqueConstraint("task_id", name="uk_document_task_task_id"),
        Index("idx_document_task_document_id", "document_id"),
        Index("idx_document_task_status", "status"),
        Index("idx_document_task_type_status", "task_type", "status"),
        Index("idx_document_task_celery_task_id", "celery_task_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    task_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class TaskAttemptModel(Base, BaseEntity):
    """文档 ETL 任务执行尝试表：记录每次 worker 执行的结果和错误摘要。"""

    __tablename__ = "document_task_attempt"
    __table_args__ = (
        UniqueConstraint("task_id", "attempt_no", name="uk_task_attempt_no"),
        Index("idx_task_attempt_task_id", "task_id"),
        Index("idx_task_attempt_status", "status"),
        Index("idx_task_attempt_celery_task_id", "celery_task_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempt_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
