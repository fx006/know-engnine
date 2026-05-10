from datetime import date

from sqlalchemy import JSON, Date, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from know_engine_py.app.models.base import Base, BaseEntity


class KnowledgeDocumentModel(Base, BaseEntity):
    __tablename__ = "knowledge_document"
    __table_args__ = (
        Index("idx_knowledge_document_status", "status"),
        Index("idx_knowledge_document_status_doc_id", "status", "doc_id"),
        Index("idx_knowledge_document_created_at", "created_at"),
    )

    doc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_title: Mapped[str] = mapped_column(String(1024), nullable=False)
    upload_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doc_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    converted_doc_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    expire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    accessible_by: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    knowledge_base_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Java 版 extension 是 JSON 字符串；Python 版直接用 dict，业务层不用反复手动解析。
    extension: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class KnowledgeSegmentModel(Base, BaseEntity):
    __tablename__ = "knowledge_segment"
    __table_args__ = (
        Index("idx_knowledge_segment_document_id", "document_id"),
        Index("idx_knowledge_segment_document_order", "document_id", "chunk_order"),
        Index(
            "idx_knowledge_segment_document_status_skip",
            "document_id",
            "status",
            "skip_embedding",
        ),
        Index("idx_knowledge_segment_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # SQLAlchemy 保留了 metadata，所以这里用 extra_metadata 映射数据库列 metadata。
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_order: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skip_embedding: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TableMetaModel(Base, BaseEntity):
    __tablename__ = "table_meta"
    __table_args__ = (
        UniqueConstraint("table_name", name="uk_table_meta_table_name"),
        Index("idx_table_meta_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    create_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    columns_info: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
