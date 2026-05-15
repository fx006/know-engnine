from __future__ import annotations

from typing import Any

from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore


class MilvusRetrieverFactory:
    """把 LangChain Milvus VectorStore 转成 Retriever。"""

    def __init__(
        self,
        vector_store: VectorStore,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ):
        self.vector_store = vector_store
        self.top_k = top_k
        self.metadata_filter = metadata_filter

    def create(self) -> BaseRetriever:
        """创建 Milvus 向量检索器，供 HybridRetriever 或 LangGraph node 使用。"""
        self._validate_config()

        search_kwargs: dict[str, Any] = {"k": self.top_k}

        if self.metadata_filter:
            search_kwargs["filter"] = self.metadata_filter

        return self.vector_store.as_retriever(search_kwargs=search_kwargs)

    def _validate_config(self) -> None:
        if self.top_k <= 0:
            raise ValueError("top_k 必须大于 0")