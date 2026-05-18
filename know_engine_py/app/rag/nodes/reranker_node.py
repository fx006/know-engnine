from __future__ import annotations

from collections.abc import Awaitable, Callable

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

        return {
            **state,
            "selected_docs": selected_docs,
            "progress_messages": progress_messages,
        }

    return reranker_node