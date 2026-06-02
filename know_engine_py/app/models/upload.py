from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from know_engine_py.app.models.base import Base, BaseEntity


class FileObjectModel(Base, BaseEntity):
    """完整文件对象表：记录已完成上传且可复用的对象存储文件。"""

    __tablename__ = "file_object"
    __table_args__ = (
        UniqueConstraint("file_object_id", name="uk_file_object_file_object_id"),
        Index("idx_file_object_file_hash", "file_hash"),
        Index("idx_file_object_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    file_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_name: Mapped[str] = mapped_column(String(2048), nullable=False)
    file_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)


class UploadSessionModel(Base, BaseEntity):
    """分片上传会话表：记录一个大文件上传过程的可恢复状态。"""

    __tablename__ = "upload_session"
    __table_args__ = (
        UniqueConstraint("upload_id", name="uk_upload_session_upload_id"),
        Index("idx_upload_session_file_hash", "file_hash"),
        Index("idx_upload_session_created_by", "created_by"),
        Index("idx_upload_session_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(String(64), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    file_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    object_name: Mapped[str] = mapped_column(String(2048), nullable=False)
    file_object_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)


class UploadChunkModel(Base, BaseEntity):
    """分片上传块表：记录已经成功保存到对象存储的单个分片。"""

    __tablename__ = "upload_chunk"
    __table_args__ = (
        UniqueConstraint("upload_id", "chunk_index", name="uk_upload_chunk_session_index"),
        Index("idx_upload_chunk_upload_id", "upload_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_name: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
