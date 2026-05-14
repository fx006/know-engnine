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
