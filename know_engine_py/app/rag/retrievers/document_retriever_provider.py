from __future__ import annotations

from typing import Any, Literal, Type

from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore

from know_engine_py.app.core.settings import Settings, get_settings
from know_engine_py.app.rag.retrievers.elasticsearch_keyword import (
    ElasticsearchKeywordRetrieverFactory,
)
from know_engine_py.app.rag.retrievers.hybrid import HybridRetriever
from know_engine_py.app.rag.retrievers.milvus import MilvusRetrieverFactory
from know_engine_py.app.rag.vectorstores.milvus import MilvusVectorStoreFactory
from know_engine_py.app.rag.retrievers.scope import RetrievalScope

DocumentRetrievalStrategy = Literal["auto", "hybrid_document", "vector", "keyword"]


class UnavailableRetriever(BaseRetriever):
    """环境未配置时使用的显式不可用 retriever。

    它比返回空列表更安全：空列表像是“检索到了但没结果”，
    不可用 retriever 表达的是“检索能力还没接好”。
    """

    reason: str

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        raise RuntimeError(self.reason)

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: AsyncCallbackManagerForRetrieverRun,
    ) -> list[Document]:
        raise RuntimeError(self.reason)


class DocumentRetrieverProvider:
    """文档检索器提供者。

    根据当前 Settings 组装 Milvus、Elasticsearch 或 HybridRetriever。
    它只处理文档检索通道，不负责 SQL/Neo4j/LLM route 决策。
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        top_k: int = 5,
        milvus_vectorstore_factory_cls: Type[MilvusVectorStoreFactory] = MilvusVectorStoreFactory,
        milvus_retriever_factory_cls: Type[MilvusRetrieverFactory] = MilvusRetrieverFactory,
        keyword_retriever_factory_cls: Type[
            ElasticsearchKeywordRetrieverFactory
        ] = ElasticsearchKeywordRetrieverFactory,
        hybrid_retriever_cls: Type[HybridRetriever] = HybridRetriever,
    ):
        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        self.settings = settings or get_settings()
        self.top_k = top_k
        self.milvus_vectorstore_factory_cls = milvus_vectorstore_factory_cls
        self.milvus_retriever_factory_cls = milvus_retriever_factory_cls
        self.keyword_retriever_factory_cls = keyword_retriever_factory_cls
        self.hybrid_retriever_cls = hybrid_retriever_cls

    def create(
        self,
        strategy: DocumentRetrievalStrategy | str = "auto",
        scope: RetrievalScope | None = None,
    ) -> BaseRetriever:
        """按指定文档检索策略创建检索器。

        settings 表达“当前环境有哪些检索能力可用”；
        strategy 表达“本次查询想使用哪个文档检索能力”。
        scope 表达“本次查询允许访问哪个知识空间”。
        """
        normalized_strategy = self._normalize_strategy(strategy)
        metadata_filter = self._scope_to_metadata_filter(scope)

        if normalized_strategy == "auto":
            return self._create_auto_retriever(metadata_filter=metadata_filter)

        if normalized_strategy == "hybrid_document":
            return self._create_hybrid_document_retriever(
                metadata_filter=metadata_filter
            )

        if normalized_strategy == "vector":
            if not self._milvus_enabled():
                return self._unavailable("文档向量检索不可用：MILVUS_URI 未配置")
            return self._create_milvus_retriever(metadata_filter=metadata_filter)

        if normalized_strategy == "keyword":
            if not self._elasticsearch_enabled():
                return self._unavailable("文档关键词检索不可用：ELASTICSEARCH_URL 未配置")
            return self._create_keyword_retriever(metadata_filter=metadata_filter)

        raise ValueError(f"不支持的文档检索策略：{strategy}")

    def _create_auto_retriever(
        self,
        *,
        metadata_filter: dict[str, Any] | None = None,
    ) -> BaseRetriever:
        """根据环境自动选择默认文档检索器。

        auto 是环境兜底策略；业务路由明确时应传入 hybrid_document/vector/keyword。
        """
        retrievers: list[BaseRetriever] = []
        source_names: list[str] = []

        if self._milvus_enabled():
            retrievers.append(
                self._create_milvus_retriever(metadata_filter=metadata_filter)
            )
            source_names.append("vector")

        if self._elasticsearch_enabled():
            retrievers.append(
                self._create_keyword_retriever(metadata_filter=metadata_filter)
            )
            source_names.append("keyword")

        if not retrievers:
            return self._unavailable(
                "文档检索不可用：请至少配置 MILVUS_URI 或 ELASTICSEARCH_URL。"
                "当前无法执行知识库召回。"
            )

        if len(retrievers) == 1:
            return retrievers[0]

        return self.hybrid_retriever_cls(
            retrievers=retrievers,
            source_names=source_names,
            top_k=self.top_k,
        )

    def _create_hybrid_document_retriever(
        self,
        *,
        metadata_filter: dict[str, Any] | None = None,
    ) -> BaseRetriever:
        """创建明确的文档混合检索器，要求 Milvus 和 ES 都可用。"""
        missing_settings: list[str] = []
        if not self._milvus_enabled():
            missing_settings.append("MILVUS_URI")
        if not self._elasticsearch_enabled():
            missing_settings.append("ELASTICSEARCH_URL")

        if missing_settings:
            return self._unavailable(
                "文档混合检索不可用：缺少 "
                + "、".join(missing_settings)
            )

        return self.hybrid_retriever_cls(
            retrievers=[
                self._create_milvus_retriever(metadata_filter=metadata_filter),
                self._create_keyword_retriever(metadata_filter=metadata_filter),
            ],
            source_names=["vector", "keyword"],
            top_k=self.top_k,
        )

    def _create_milvus_retriever(
        self,
        *,
        metadata_filter: dict[str, Any] | None = None,
    ) -> BaseRetriever:
        vector_store = self._create_milvus_vector_store()
        return self.milvus_retriever_factory_cls(
            vector_store=vector_store,
            top_k=self.top_k,
            metadata_filter=metadata_filter,
        ).create()

    def _create_milvus_vector_store(self) -> VectorStore:
        return self.milvus_vectorstore_factory_cls(
            settings=self.settings,
        ).create()

    def _create_keyword_retriever(
        self,
        *,
        metadata_filter: dict[str, Any] | None = None,
    ) -> BaseRetriever:
        return self.keyword_retriever_factory_cls(
            settings=self.settings,
            top_k=self.top_k,
            metadata_filter=metadata_filter,
        ).create()

    def _milvus_enabled(self) -> bool:
        return bool(self.settings.milvus_uri.strip())

    def _elasticsearch_enabled(self) -> bool:
        return bool(self.settings.elasticsearch_url.strip())

    def _unavailable(self, reason: str) -> UnavailableRetriever:
        return UnavailableRetriever(reason=reason)

    def _normalize_strategy(self, strategy: DocumentRetrievalStrategy | str) -> str:
        value = str(strategy or "").strip().lower()
        aliases = {
            "auto": "auto",
            "hybrid": "hybrid_document",
            "hybrid_document": "hybrid_document",
            "document_hybrid": "hybrid_document",
            "vector": "vector",
            "keyword": "keyword",
        }

        normalized = aliases.get(value)
        if normalized is None:
            raise ValueError(f"不支持的文档检索策略：{strategy}")
        return normalized

    def _scope_to_metadata_filter(
        self,
        scope: RetrievalScope | None,
    ) -> dict[str, str]:
        if scope is None:
            return {}

        return scope.to_metadata_filter()
