from __future__ import annotations

from collections.abc import Iterable

from langchain_core.documents import Document


def documents_to_ragas_contexts(documents: Iterable[Document]) -> list[str]:
    """将召回的 LangChain Document 转成 RAGAS 使用的纯文本上下文。"""

    contexts: list[str] = []
    for document in documents:
        context = document_to_ragas_context(document)
        if context:
            contexts.append(context)
    return contexts


def document_to_ragas_context(document: Document) -> str:
    """将单个召回结果转成 RAGAS 使用的文本上下文。

    Text-to-SQL 结果不是普通 chunk，需要稳定的文本外壳，让忠实性评分同时看到
    SQL 证据和结果摘要。
    """

    metadata = dict(document.metadata or {})
    if _is_text_to_sql(metadata):
        sql = str(metadata.get("executedSql") or metadata.get("sql") or "").strip()
        tables = ", ".join(_to_string_list(metadata.get("tables"))) or "无"
        row_count = metadata.get("rowCount") or metadata.get("row_count")
        result_summary = document.page_content.strip()

        parts = [
            "结构化查询结果",
            f"SQL: {sql or '无'}",
            f"涉及表: {tables}",
        ]
        if row_count not in (None, ""):
            parts.append(f"结果行数: {row_count}")
        parts.append(f"结果摘要: {result_summary or '无'}")
        return "\n".join(parts)

    return document.page_content.strip()


def _is_text_to_sql(metadata: dict) -> bool:
    route = str(
        metadata.get("retrievalRoute") or metadata.get("retrievalSource") or ""
    ).lower()
    return route == "text2sql"


def _to_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value]
    return [str(value)]
