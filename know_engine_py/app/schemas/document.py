from pydantic import BaseModel, ConfigDict, Field

from know_engine_py.app.rag.splitters.types import DocumentSplitParam, SplitType


class DocumentResponse(BaseModel):
    """文档接口响应模型，对应 KnowledgeDocument 的前端可见字段。"""

    model_config = ConfigDict(from_attributes=True)

    doc_id: int
    doc_title: str
    upload_user: str | None = None
    doc_url: str | None = None
    converted_doc_url: str | None = None
    status: str
    accessible_by: str | None = None
    description: str | None = None
    knowledge_base_type: str | None = None
    group_id: str | None = None
    knowledge_base_id: str | None = None
    file_object_id: str | None = None
    extension: dict | None = None


class SegmentResponse(BaseModel):
    """文档分段响应模型，对应 KnowledgeSegment 的前端可见字段。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    segment_id: int = Field(alias="id")
    document_id: int
    chunk_id: str | None = None
    chunk_order: int
    text: str
    status: str
    skip_embedding: int
    extra_metadata: dict | None = None


class DocumentSplitRequest(BaseModel):
    """触发文档切分的请求体。"""

    split_type: SplitType = Field(default=SplitType.TITLE, alias="splitType")
    chunk_size: int = Field(default=800, alias="chunkSize", gt=0)
    overlap: int = Field(default=80, ge=0)
    title_level: int = Field(default=1, alias="titleLevel", gt=0)
    regex: str | None = None
    separator: str | None = None

    model_config = ConfigDict(populate_by_name=True)

    def to_split_param(self) -> DocumentSplitParam:
        """转换成 splitter 层内部参数对象，避免 service 依赖 API schema。"""
        return DocumentSplitParam(
            split_type=self.split_type,
            chunk_size=self.chunk_size,
            overlap=self.overlap,
            title_level=self.title_level,
            regex=self.regex,
            separator=self.separator,
        )


class DocumentSplitResponse(BaseModel):
    """文档切分响应：包含切分数量和后续索引任务投递结果。"""

    model_config = ConfigDict(populate_by_name=True)

    document_id: int = Field(alias="documentId")
    segment_count: int = Field(alias="segmentCount")
    index_queued: bool = Field(alias="indexQueued")
    index_task_id: str | None = Field(default=None, alias="indexTaskId")
    index_queue_error: str | None = Field(default=None, alias="indexQueueError")


class DocumentImportResponse(DocumentResponse):
    """文档导入响应：包含导入结果和后续转换任务投递结果。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    conversion_queued: bool = Field(default=False, alias="conversionQueued")
    conversion_task_id: str | None = Field(default=None, alias="conversionTaskId")
    conversion_queue_error: str | None = Field(default=None, alias="conversionQueueError")
