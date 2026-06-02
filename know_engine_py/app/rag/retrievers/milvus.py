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

        metadata_expr = _build_milvus_metadata_expr(self.metadata_filter or {})
        if metadata_expr:
            search_kwargs["expr"] = metadata_expr

        return self.vector_store.as_retriever(search_kwargs=search_kwargs)

    def _validate_config(self) -> None:
        if self.top_k <= 0:
            raise ValueError("top_k 必须大于 0")


def _build_milvus_metadata_expr(metadata_filter: dict[str, Any]) -> str | None:
    """把平台 metadata filter 翻译成 Milvus expr。

    当前 Milvus VectorStore 使用 metadata_field="metadata"，权限字段位于 JSON metadata 中；
    兼容少量标量字段过滤，方便测试和未来显式 schema 演进。
    """
    expressions: list[str] = []

    for key, value in metadata_filter.items():
        if value in (None, ""):
            continue

        if isinstance(value, bool):
            value_expr = "true" if value else "false"
        elif isinstance(value, int | float):
            value_expr = str(value)
        else:
            value_expr = f'"{_escape_milvus_string(str(value))}"'

        field_expr = _milvus_field_expr(key)
        expressions.append(f"{field_expr} == {value_expr}")

    if not expressions:
        return None

    return " and ".join(expressions)


def _milvus_field_expr(key: str) -> str:
    if key in {"groupId", "knowledgeBaseId"}:
        return f'metadata["{key}"]'

    return key


def _escape_milvus_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
