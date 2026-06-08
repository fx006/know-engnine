from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain_core.documents import Document

from know_engine_py.app.rag.rerankers.base import DocumentReranker
from know_engine_py.app.rag.state import AgentState


RerankerNode = Callable[[AgentState], Awaitable[AgentState]]


def create_reranker_node(
    reranker: DocumentReranker,
    *,
    top_k: int = 5,
) -> RerankerNode:
    """创建文档重排序节点。

    节点只负责编排：取 query 和 retrieved_docs，调用 reranker，然后把结果写回
    selected_docs。具体模型选择留给 reranker 实现类。
    """

    async def reranker_node(state: AgentState) -> AgentState:
        progress_messages = [
            *state.get("progress_messages", []),
            "[PROGRESS]:正在排序筛选结果...",
        ]
        documents = state.get("retrieved_docs") or []

        if not documents:
            return {
                **state,
                "selected_docs": [],
                "progress_messages": progress_messages,
            }

        query = state.get("transformed_query") or state["query"]

        try:
            selected_docs = await reranker.arerank(
                query,
                documents,
                top_k=top_k,
            )
        except Exception:
            # rerank 是增强能力，失败时保留原始召回结果，避免打断主问答链路。
            selected_docs = documents[:top_k]

        selected_docs = _keep_required_structured_documents(
            selected_docs=selected_docs,
            retrieved_docs=documents,
            top_k=top_k,
        )

        return {
            **state,
            "selected_docs": selected_docs,
            "progress_messages": progress_messages,
        }

    return reranker_node


def _keep_required_structured_documents(
    *,
    selected_docs: list[Document],
    retrieved_docs: list[Document],
    top_k: int | None,
) -> list[Document]:
    """保证 Text-to-SQL 这类结构化结果不会被文档分数挤出上下文。

    multi-route 问题通常需要“文档规则 + 业务表结果”共同回答。轻量 metadata
    reranker 只看检索分数，SQL 文档没有向量/关键词分数时容易被 top_k 截断。
    """
    required_docs = [
        document
        for document in retrieved_docs
        if _is_required_structured_document(document)
    ]
    if not required_docs:
        return selected_docs

    selected_keys = {_document_key(document) for document in selected_docs}
    missing_docs = [
        document
        for document in required_docs
        if _document_key(document) not in selected_keys
    ]
    if not missing_docs:
        return selected_docs

    if top_k is None:
        return [*selected_docs, *missing_docs]

    missing_docs = missing_docs[:top_k]
    keep_count = max(top_k - len(missing_docs), 0)
    return [*selected_docs[:keep_count], *missing_docs]


def _is_required_structured_document(document: Document) -> bool:
    metadata = dict(document.metadata or {})
    route_fields = {
        str(value)
        for value in (
            metadata.get("retrievalRoute"),
            metadata.get("retrievalSource"),
            metadata.get("sourceType"),
        )
        if value
    }
    if "text2sql" not in route_fields:
        return False

    # fallback 文档只是 Text-to-SQL 失败后的知识库兜底，不应被当成 SQL 结果强保留。
    return bool(metadata.get("sql") or metadata.get("executedSql"))


def _document_key(document: Document) -> str:
    metadata = dict(document.metadata or {})
    for key in ("sql", "executedSql", "chunkId", "chunk_id", "retrievalKey"):
        value = metadata.get(key)
        if value:
            return f"{key}:{value}"

    if document.id:
        return f"id:{document.id}"

    return f"text:{document.page_content}"
