from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal, TypedDict

from langchain_core.documents import Document


class RagReference(TypedDict, total=False):
    """前端和消息表都能使用的 RAG 引用结构，对齐 Java ChatMessage.RagReference。"""

    sourceType: str
    documentId: str | None
    url: str | None
    documentTitle: str | None
    chunkId: str | None
    chunkContent: str
    similarityScore: float | None
    rerankScore: float | None
    retrievalSource: str
    sql: str | None
    executedSql: str | None
    tables: list[str]
    rowCount: int | None
    truncated: bool | None
    success: bool | None
    error: str | None
    metadata: dict[str, Any]


DedupeKey = Literal["chunkId", "documentId", "sql"]


def build_rag_reference(
    document: Document,
) -> RagReference:
    """将 LangChain Document 转成项目内部引用结构。

    Java 版从 Content.textSegment().metadata() 取 docId、fileName、url、chunkId。
    Python 版对应从 Document.metadata 取值，并兼容少量历史/框架字段名。
    """
    metadata = dict(document.metadata or {})
    if _is_text_to_sql_reference(metadata):
        return _build_text_to_sql_reference(document, metadata=metadata)

    return {
        "sourceType": "document",
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
        "retrievalSource": _resolve_retrieval_source(metadata),
        "metadata": metadata,
    }


def build_rag_references(
    documents: Iterable[Document],
    *,
    require_chunk_id: bool = True,
    dedupe_by: DedupeKey = "chunkId",
) -> list[RagReference]:
    """批量构建引用列表。

    文档引用要求有 chunkId，避免把普通回答内容误当知识库引用。
    Text-to-SQL 引用没有 chunkId，但会带 sourceType=text2sql 和 SQL 元数据。
    """
    references: list[RagReference] = []
    seen: set[str] = set()

    for document in documents:
        reference = build_rag_reference(document)

        if (
            require_chunk_id
            and reference.get("sourceType") != "text2sql"
            and not reference.get("chunkId")
        ):
            continue

        dedupe_value = _reference_dedupe_value(reference, dedupe_by)
        if dedupe_value:
            if dedupe_value in seen:
                continue
            seen.add(dedupe_value)

        references.append(reference)

    return references


def _build_text_to_sql_reference(
    document: Document,
    *,
    metadata: dict[str, Any],
) -> RagReference:
    """构造结构化查询引用。

    SQL 结果不是知识库 chunk，不能伪造 chunkId；用 sourceType 区分后，
    前端和消息表可以用同一个 rag_references JSON 字段承载不同来源。
    """
    return {
        "sourceType": "text2sql",
        "documentId": None,
        "url": None,
        "documentTitle": "结构化查询结果",
        "chunkId": None,
        "chunkContent": document.page_content,
        "similarityScore": None,
        "rerankScore": None,
        "retrievalSource": "text2sql",
        "sql": _to_string(_first_value(metadata, "sql")),
        "executedSql": _to_string(_first_value(metadata, "executedSql", "executed_sql")),
        "tables": _to_string_list(metadata.get("tables")),
        "rowCount": _to_int(_first_value(metadata, "rowCount", "row_count")),
        "truncated": _to_bool(metadata.get("truncated")),
        "success": _to_bool(metadata.get("success")),
        "error": _to_string(_first_value(metadata, "error")),
        "metadata": metadata,
    }


def _is_text_to_sql_reference(metadata: dict[str, Any]) -> bool:
    source = str(metadata.get("retrievalSource") or metadata.get("retrievalRoute") or "")
    return source.lower() == "text2sql"


def _reference_dedupe_value(reference: RagReference, dedupe_by: DedupeKey) -> str | None:
    value = reference.get(dedupe_by)
    if value:
        return str(value)

    if reference.get("sourceType") == "text2sql":
        sql = reference.get("executedSql") or reference.get("sql")
        if sql:
            return f"text2sql:{sql}"
        return f"text2sql:{reference.get('chunkContent')}"

    return None


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


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def _to_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple | set):
        return [str(item) for item in value]
    return [str(value)]


def _resolve_retrieval_source(
    metadata: dict[str, Any],
) -> str:
    source = metadata.get("retrievalSource")
    if source:
        return str(source)

    route = metadata.get("retrievalRoute")
    if route:
        return str(route)

    sources = metadata.get("retrievalSources")
    if isinstance(sources, list) and sources:
        if len(sources) > 1:
            return "hybrid"
        return str(sources[0])

    return "unknown"
