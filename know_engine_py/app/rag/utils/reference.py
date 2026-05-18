from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal, TypedDict

from langchain_core.documents import Document


class RagReference(TypedDict, total=False):
    """前端和消息表都能使用的 RAG 引用结构，对齐 Java ChatMessage.RagReference。"""

    documentId: str | None
    url: str | None
    documentTitle: str | None
    chunkId: str | None
    chunkContent: str
    similarityScore: float | None
    rerankScore: float | None
    retrievalSource: str
    metadata: dict[str, Any]


DedupeKey = Literal["chunkId", "documentId"]


def build_rag_reference(
    document: Document,
    *,
    retrieval_source: str | None = None,
) -> RagReference:
    """将 LangChain Document 转成项目内部引用结构。

    Java 版从 Content.textSegment().metadata() 取 docId、fileName、url、chunkId。
    Python 版对应从 Document.metadata 取值，并兼容少量历史/框架字段名。
    """
    metadata = dict(document.metadata or {})

    return {
        "documentId": _to_string(
            _first_value(metadata, "docId", "documentId", "document_id")
        ),
        "url": _to_string(_first_value(metadata, "url", "docUrl", "sourceUrl")),
        "documentTitle": _to_string(
            _first_value(metadata, "fileName", "documentTitle", "docTitle", "title")
        ),
        "chunkId": _to_string(_first_value(metadata, "chunkId", "chunk_id")),
        "chunkContent": document.page_content,
        "similarityScore": _to_float(
            _first_value(metadata, "similarityScore", "score", "_score", "rrfScore")
        ),
        "rerankScore": _to_float(
            _first_value(metadata, "rerankScore", "rerankedScore")
        ),
        "retrievalSource": _resolve_retrieval_source(metadata, retrieval_source),
        "metadata": metadata,
    }


def build_rag_references(
    documents: Iterable[Document],
    *,
    retrieval_source: str | None = "hybrid",
    require_chunk_id: bool = True,
    dedupe_by: DedupeKey = "chunkId",
) -> list[RagReference]:
    """批量构建引用列表。

    当前知识库引用要求有 chunkId；后续 Text-to-SQL/Neo4j 如果没有 chunkId，
    可以单独放宽 require_chunk_id 或设计新的 reference type。
    """
    references: list[RagReference] = []
    seen: set[str] = set()

    for document in documents:
        reference = build_rag_reference(
            document,
            retrieval_source=retrieval_source,
        )

        if require_chunk_id and not reference.get("chunkId"):
            continue

        dedupe_value = reference.get(dedupe_by)
        if dedupe_value:
            if dedupe_value in seen:
                continue
            seen.add(dedupe_value)

        references.append(reference)

    return references


def _first_value(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata and metadata[key] not in (None, ""):
            return metadata[key]
    return None


def _to_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_retrieval_source(
    metadata: dict[str, Any],
    explicit_source: str | None,
) -> str:
    if explicit_source:
        return explicit_source

    source = metadata.get("retrievalSource")
    if source:
        return str(source)

    sources = metadata.get("retrievalSources")
    if isinstance(sources, list) and sources:
        if len(sources) > 1:
            return "hybrid"
        return str(sources[0])

    return "unknown"