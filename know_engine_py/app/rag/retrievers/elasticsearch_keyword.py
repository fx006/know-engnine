from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_elasticsearch import AsyncElasticsearchRetriever

from know_engine_py.app.core.settings import Settings, get_settings


def build_keyword_query(
    query: str,
    *,
    top_k: int = 5,
    metadata_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造 Elasticsearch BM25 关键词检索请求体。"""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("检索关键词不能为空")
    if top_k <= 0:
        raise ValueError("top_k 必须大于 0")

    keyword_query = {
        "multi_match": {
            "query": normalized_query,
            "fields": [
                "text^3",
                "metadata.headingPath^2",
                "metadata.keywords^2",
                "metadata.fileName",
            ],
            "type": "best_fields",
        }
    }

    filters = _build_metadata_filters(metadata_filter or {})
    if not filters:
        return {
            "query": keyword_query,
            "size": top_k,
        }

    return {
        "query": {
            "bool": {
                "must": [keyword_query],
                "filter": filters,
            }
        },
        "size": top_k,
    }


def map_elasticsearch_hit(hit: Mapping[str, Any]) -> Document:
    """把 Elasticsearch 原始 hit 转成 LangChain Document。"""
    source = hit.get("_source") or {}
    metadata = dict(source.get("metadata") or {})

    # score/esId 是检索阶段产生的字段，不写入正文，放 metadata 供引用排序和调试使用。
    metadata.setdefault("score", hit.get("_score"))
    metadata.setdefault("esId", hit.get("_id"))

    return Document(
        page_content=source.get("text") or "",
        metadata=metadata,
    )


class ElasticsearchKeywordRetrieverFactory:
    """创建基于 Elasticsearch BM25 的 LangChain async retriever。"""

    def __init__(
        self,
        settings: Settings | None = None,
        retriever_cls: Callable[..., BaseRetriever] = AsyncElasticsearchRetriever,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ):
        self.settings = settings or get_settings()
        self.retriever_cls = retriever_cls
        self.top_k = top_k
        self.metadata_filter = metadata_filter or {}

    def create(self) -> BaseRetriever:
        """根据项目配置创建 Elasticsearch 关键词检索器。"""
        self._validate_settings()

        return self.retriever_cls(
            index_name=self.settings.elasticsearch_index,
            es_url=self.settings.elasticsearch_url,
            body_func=self._build_body,
            document_mapper=map_elasticsearch_hit,
        )

    def _build_body(self, query: str) -> dict[str, Any]:
        return build_keyword_query(
            query,
            top_k=self.top_k,
            metadata_filter=self.metadata_filter,
        )

    def _validate_settings(self) -> None:
        if not self.settings.elasticsearch_url.strip():
            raise ValueError("ELASTICSEARCH_URL 不能为空")


def _build_metadata_filters(metadata_filter: dict[str, Any]) -> list[dict[str, Any]]:
    """把平台 metadata 过滤条件翻译成 Elasticsearch bool filter。

    ES 索引里 metadata 是对象字段；权限字段是精确值匹配，走 keyword 子字段。
    """
    filters: list[dict[str, Any]] = []

    for key, value in metadata_filter.items():
        if value in (None, ""):
            continue

        filters.append({"term": {f"metadata.{key}.keyword": str(value)}})

    return filters
