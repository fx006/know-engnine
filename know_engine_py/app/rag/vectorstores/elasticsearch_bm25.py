from __future__ import annotations

from collections.abc import Callable

from langchain_core.vectorstores import VectorStore
from langchain_elasticsearch import AsyncBM25Strategy, AsyncElasticsearchStore

from know_engine_py.app.core.settings import Settings, get_settings


class ElasticsearchBM25StoreFactory:
    """创建用于关键词索引写入的 LangChain Elasticsearch Store。"""

    def __init__(
        self,
        settings: Settings | None = None,
        store_cls: Callable[..., VectorStore] = AsyncElasticsearchStore,
    ):
        self.settings = settings or get_settings()
        self.store_cls = store_cls

    def create(self) -> VectorStore:
        """创建纯 BM25 文本索引 store，不在 ES 里生成向量。"""
        self._validate_settings()

        return self.store_cls(
            index_name=self.settings.elasticsearch_index,
            es_url=self.settings.elasticsearch_url,
            embedding=None,
            strategy=AsyncBM25Strategy(),
            query_field="text",
        )

    def _validate_settings(self) -> None:
        if not self.settings.elasticsearch_url.strip():
            raise ValueError("ELASTICSEARCH_URL 不能为空")

        if not self.settings.elasticsearch_index.strip():
            raise ValueError("ELASTICSEARCH_INDEX 不能为空")