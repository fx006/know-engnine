from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from langchain_core.documents import Document

from know_engine_py.app.rag.state import AgentState


class AsyncRetriever(Protocol):
    """retrieve_node 只依赖 LangChain retriever 的异步调用约定。"""

    async def ainvoke(self, query: str) -> list[Document]:
        ...


RetrieveNode = Callable[[AgentState], Awaitable[AgentState]]


def create_retrieve_node(retriever: AsyncRetriever) -> RetrieveNode:
    """创建检索节点。

    Day6 基础图先使用一个已组装好的 retriever；后续 SQL、Neo4j、rerank 会在
    这个节点之后继续加厚，不在这里重复实现检索融合。
    """

    async def retrieve_node(state: AgentState) -> AgentState:
        progress_messages = [
            *state.get("progress_messages", []),
            "[PROGRESS]:正在检索相关资料...",
        ]
        query = state.get("transformed_query") or state["query"]

        try:
            documents = await retriever.ainvoke(query)
        except Exception as exc:
            return {
                **state,
                "retrieved_docs": [],
                "selected_docs": [],
                "progress_messages": progress_messages,
                "error": f"检索失败：{exc}",
            }

        return {
            **state,
            "retrieved_docs": documents,
            "selected_docs": documents,
            "progress_messages": progress_messages,
            "error": None,
        }

    return retrieve_node
