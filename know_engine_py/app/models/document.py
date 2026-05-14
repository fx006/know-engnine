from datetime import date

from sqlalchemy import JSON, Date, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from know_engine_py.app.models.base import Base, BaseEntity


class KnowledgeDocumentModel(Base, BaseEntity):
    """知识文档主表：记录文档从上传到切分、向量化的生命周期。"""

    __tablename__ = "knowledge_document"
    __table_args__ = (
        # 按状态筛选文档（例如待处理、已切分、已向量化）时使用。
        Index("idx_knowledge_document_status", "status"),
        # 管理端按状态分页时，通常会带 doc_id 做游标或排序辅助。
        Index("idx_knowledge_document_status_doc_id", "status", "doc_id"),
        # 便于按创建时间倒序查看最新上传文档。
        Index("idx_knowledge_document_created_at", "created_at"),
    )

    # 文档主键，对应业务里的 documentId / docId。
    doc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 文档标题（列表展示、检索引用展示、管理后台检索）。
    doc_title: Mapped[str] = mapped_column(String(1024), nullable=False)
    # 上传人标识（用户名、员工号或系统账号），用于审计和过滤。
    upload_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 原始文档地址（本地路径或对象存储 URL）。
    doc_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # 转换后的文本/Markdown 地址（切分时优先读取这里）。
    converted_doc_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # 文档失效日期，过期后可在检索或召回阶段做过滤。
    expire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 文档生命周期状态，例如 INIT/UPLOADED/CONVERTED/CHUNKED/VECTOR_STORED。
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # 访问范围控制（部门、角色、租户或用户列表）。
    accessible_by: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # 人工备注，便于后台管理和排障。
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 知识库类型（如通用知识库、数据问答知识库等）。
    knowledge_base_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Java 版 extension 是 JSON 字符串；Python 版直接用 dict，业务层不用反复手动解析。
    # 预留扩展字段：可放来源系统、标签、处理参数快照等。
    extension: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class KnowledgeSegmentModel(Base, BaseEntity):
    """文档切片表：保存 chunk 文本和检索相关元数据。"""

    __tablename__ = "knowledge_segment"
    __table_args__ = (
        # 最常见查询：按 document_id 拉取某文档全部切片。
        Index("idx_knowledge_segment_document_id", "document_id"),
        # 拉取文档切片时按 chunk_order 排序，保证上下文顺序稳定。
        Index("idx_knowledge_segment_document_order", "document_id", "chunk_order"),
        Index(
            # 用于找“某文档中待向量化且不跳过 embedding 的切片”。
            "idx_knowledge_segment_document_status_skip",
            "document_id",
            "status",
            "skip_embedding",
        ),
        # 便于按状态批处理切片（补偿任务、重试任务）。
        Index("idx_knowledge_segment_status", "status"),
    )

    # 切片记录主键（数据库内部 ID）。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 切片正文内容（最终进入向量库和关键词检索库的核心文本）。
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # 业务切片 ID（用于引用溯源、去重、跨系统关联）。
    chunk_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # SQLAlchemy 保留了 metadata，所以这里用 extra_metadata 映射数据库列 metadata。
    # 切片元数据：常见包含 docId/fileName/url/parentChunkId/brotherChunkId 等。
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    # 所属文档 ID（逻辑外键，关联 knowledge_document.doc_id）。
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 切片顺序（用于还原原文阅读顺序和拼接上下文）。
    chunk_order: Mapped[int] = mapped_column(Integer, nullable=False)
    # 向量库或检索库写入后的外部 ID（写库成功后回填）。
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 切片状态，例如 STORED/VECTOR_STORED，用于处理流水线推进。
    status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 是否跳过 embedding：1=跳过（通常是父 chunk），0/None=参与向量化。
    skip_embedding: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TableMetaModel(Base, BaseEntity):
    """结构化表元信息：给 SQL/表格问答场景提供表结构语义。"""

    __tablename__ = "table_meta"
    __table_args__ = (
        # 保证每个逻辑表只维护一份元数据。
        UniqueConstraint("table_name", name="uk_table_meta_table_name"),
        # 便于按创建时间查看或同步表元数据。
        Index("idx_table_meta_created_at", "created_at"),
    )

    # 表元数据主键。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 逻辑表名（如 order_info、vehicle_archive）。
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 表用途说明（给 LLM 选表和生成 SQL 时做语义提示）。
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 建表 SQL（回溯字段定义、主键、索引信息）。
    create_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 列信息列表（列名、类型、注释、是否主键等结构化信息）。
    columns_info: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
