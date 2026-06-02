from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models.document import KnowledgeDocumentModel, KnowledgeSegmentModel
from know_engine_py.app.models.enums import DocumentStatus, SegmentStatus


class DocumentIndexingService:
    """文档分片索引编排服务。

    对齐 Java 的 embedAndStore，但 Python 版语义更准确地叫 index_document：
    1. 只处理 CHUNKED 文档。
    2. 只向量化 STORED、未写 embedding_id、且 skip_embedding=0 的 segment。
    3. 写入向量索引，并可选写入 Elasticsearch BM25 关键词索引。
    4. 回填向量索引 id，并推进 segment/document 状态。
    """

    def __init__(
        self,
        session: AsyncSession,
        vector_store: VectorStore,
        keyword_store: VectorStore | None = None,
        batch_size: int = 100,
    ):
        self.session = session
        self.vector_store = vector_store
        self.keyword_store = keyword_store
        self.batch_size = batch_size

    async def index_document(self, document_id: int) -> bool:
        """对指定文档执行检索索引写入，全部完成返回 True，否则返回 False。"""
        document = await self._get_document(document_id)
        if document is None:
            return False

        if document.status == DocumentStatus.VECTOR_STORED.value:
            return True

        if document.status != DocumentStatus.CHUNKED.value:
            return False

        while True:
            segments = await self._list_pending_segments(document_id)
            if not segments:
                break

            documents = [
                Document(
                    id=segment.chunk_id,
                    page_content=segment.text,
                    metadata=self._build_metadata(segment),
                )
                for segment in segments
            ]

            # Milvus auto_id=False 时必须显式传主键；这里用业务 chunk_id，方便后续溯源和幂等排查。
            embedding_ids = await self.vector_store.aadd_documents(
                documents,
                ids=[segment.chunk_id for segment in segments],
            )

            if len(embedding_ids) != len(segments):
                raise ValueError("向量库返回的 embedding_id 数量与分段数量不一致")

            await self._write_keyword_index(documents)

            for segment, embedding_id in zip(segments, embedding_ids):
                segment.embedding_id = embedding_id
                segment.status = SegmentStatus.VECTOR_STORED.value

            await self.session.flush()

        remaining = await self._count_pending_segments(document_id)
        if remaining == 0:
            document.status = DocumentStatus.VECTOR_STORED.value
            await self.session.flush()
            return True

        return False

    async def _get_document(self, document_id: int) -> KnowledgeDocumentModel | None:
        result = await self.session.execute(
            select(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.doc_id == document_id
            )
        )
        return result.scalar_one_or_none()

    async def _list_pending_segments(self, document_id: int) -> list[KnowledgeSegmentModel]:
        result = await self.session.execute(
            select(KnowledgeSegmentModel)
            .where(KnowledgeSegmentModel.document_id == document_id)
            .where(KnowledgeSegmentModel.status == SegmentStatus.STORED.value)
            .where(KnowledgeSegmentModel.embedding_id.is_(None))
            .where(self._embeddable_filter())
            .order_by(KnowledgeSegmentModel.chunk_order)
            .limit(self.batch_size)
        )
        return list(result.scalars().all())

    async def _count_pending_segments(self, document_id: int) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(KnowledgeSegmentModel)
            .where(KnowledgeSegmentModel.document_id == document_id)
            .where(KnowledgeSegmentModel.status == SegmentStatus.STORED.value)
            .where(KnowledgeSegmentModel.embedding_id.is_(None))
            .where(self._embeddable_filter())
        )
        return int(result.scalar_one())

    def _build_metadata(self, segment: KnowledgeSegmentModel) -> dict:
        metadata = dict(segment.extra_metadata or {})

        # 这里做兜底，避免老数据或手工测试数据缺少 Java 检索链路依赖的关键 metadata。
        metadata.setdefault("docId", segment.document_id)
        if segment.chunk_id:
            metadata.setdefault("chunkId", segment.chunk_id)
        metadata.setdefault("skipEmbedding", segment.skip_embedding or 0)

        return metadata

    def _embeddable_filter(self):
        """兼容新旧数据：0 和 NULL 都表示需要参与 embedding。"""
        return or_(
            KnowledgeSegmentModel.skip_embedding == 0,
            KnowledgeSegmentModel.skip_embedding.is_(None),
        )

    async def _write_keyword_index(self, documents: list[Document]) -> None:
        """可选写入 Elasticsearch BM25 关键词索引。"""
        if self.keyword_store is None or not documents:
            return

        keyword_ids = await self.keyword_store.aadd_documents(documents)

        if len(keyword_ids) != len(documents):
            raise ValueError("关键词索引返回的 id 数量与分段数量不一致")
