from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.documents import Document


class DocumentReranker(Protocol):
    """文档重排序器协议。

    实现类负责根据 query 对 documents 重新排序，并把 rerankScore 写入
    Document.metadata。LangGraph node 只依赖这个协议，不绑定具体模型。
    """

    async def arerank(
        self,
        query: str,
        documents: Sequence[Document],
        *,
        top_k: int | None = None,
    ) -> list[Document]:
        ...


def copy_document_with_metadata(
    document: Document,
    metadata_updates: dict[str, Any],
) -> Document:
    """复制 Document，并合并新的 metadata，避免原地修改上游检索结果。"""
    return Document(
        id=document.id,
        page_content=document.page_content,
        metadata={**dict(document.metadata or {}), **metadata_updates},
    )