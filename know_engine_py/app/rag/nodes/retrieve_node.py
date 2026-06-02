from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from langchain_core.documents import Document

from know_engine_py.app.rag.retrievers.scope import build_retrieval_scope
from know_engine_py.app.rag.state import AgentState


class AsyncRetriever(Protocol):
    """retrieve_node 只依赖 LangChain retriever 的异步调用约定。"""

    async def ainvoke(self, query: str) -> list[Document]:
        ...


class DocumentRetrieverProviderProtocol(Protocol):
    """文档检索器提供者协议。

    retrieve_node 不直接知道 Milvus、Elasticsearch 或 HybridRetriever 怎么创建，
    只根据 route_strategy 向 provider 要一个对应的文档检索器。
    """

    def create(
        self,
        strategy: str = "auto",
        scope: RetrievalScope | None = None,
    ) -> AsyncRetriever:
        ...


RetrieveNode = Callable[[AgentState], Awaitable[AgentState]]

_DOCUMENT_RETRIEVAL_STRATEGIES = {"auto", "hybrid_document", "vector", "keyword"}
_NON_DOCUMENT_STRATEGIES = {"text2sql", "text2cypher", "multi_route"}


def create_retrieve_node(retriever: AsyncRetriever) -> RetrieveNode:
    """创建固定 retriever 的检索节点。

    这个版本适合单元测试或局部图装配：调用方已经明确传入某个 retriever，
    节点只负责执行检索并把结果写回 AgentState。
    """

    async def retrieve_node(state: AgentState) -> AgentState:
        progress_messages = _append_progress_message(state)
        query = _resolve_retrieval_query(state)

        try:
            documents = await retriever.ainvoke(query)
        except Exception as exc:
            return _failed_state(
                state,
                progress_messages=progress_messages,
                error=f"检索失败：{exc}",
            )

        return _success_state(
            state,
            documents=documents,
            progress_messages=progress_messages,
        )

    return retrieve_node


def create_document_retrieve_node(
    provider: DocumentRetrieverProviderProtocol,
) -> RetrieveNode:
    """创建按 route_strategy 选择文档检索器的节点。

    router_node 负责判断本轮应该走什么检索通道；
    这个节点只执行“文档检索”通道，包括 hybrid_document、vector、keyword。
    Text-to-SQL、Text-to-Cypher 和 multi_route 后续会有自己的执行器，
    不能混进文档 retriever provider。
    """

    async def retrieve_node(state: AgentState) -> AgentState:
        progress_messages = _append_progress_message(state)
        strategy = _resolve_document_strategy(state)

        if strategy in _NON_DOCUMENT_STRATEGIES:
            return _failed_state(
                state,
                progress_messages=progress_messages,
                error=f"当前 retrieve_node 只支持文档检索，暂不支持策略：{strategy}",
            )

        if strategy not in _DOCUMENT_RETRIEVAL_STRATEGIES:
            return _failed_state(
                state,
                progress_messages=progress_messages,
                error=f"不支持的文档检索策略：{strategy}",
            )

        query = _resolve_retrieval_query(state, strategy=strategy)

        try:
            retriever = provider.create(
                strategy=strategy,
                scope=build_retrieval_scope(state),
            )
            documents = await retriever.ainvoke(query)
        except Exception as exc:
            return _failed_state(
                state,
                progress_messages=progress_messages,
                error=f"检索失败：{exc}",
            )

        return _success_state(
            state,
            documents=documents,
            progress_messages=progress_messages,
        )

    return retrieve_node


def _resolve_document_strategy(state: AgentState) -> str:
    """从状态中读取文档检索策略；没有路由结果时退回 auto。"""
    return str(state.get("route_strategy") or "auto")


def _resolve_retrieval_query(
    state: AgentState,
    *,
    strategy: str | None = None,
) -> str:
    """解析本轮实际用于检索的 query。

    优先使用 route_plan 中对应 route 的 query；
    如果没有 route_plan，则使用 transform_node 生成的 transformed_query；
    最后退回用户原始 query。
    """
    route_plan = state.get("route_plan") or []
    if strategy:
        for route_item in route_plan:
            if route_item.get("route") == strategy and route_item.get("query"):
                return str(route_item["query"])

    return str(state.get("transformed_query") or state["query"])


def _append_progress_message(state: AgentState) -> list[str]:
    return [
        *state.get("progress_messages", []),
        "[PROGRESS]:正在检索相关资料...",
    ]


def _success_state(
    state: AgentState,
    *,
    documents: list[Document],
    progress_messages: list[str],
) -> AgentState:
    return {
        **state,
        "retrieved_docs": documents,
        "selected_docs": documents,
        "progress_messages": progress_messages,
        "error": None,
    }


def _failed_state(
    state: AgentState,
    *,
    progress_messages: list[str],
    error: str,
) -> AgentState:
    return {
        **state,
        "retrieved_docs": [],
        "selected_docs": [],
        "progress_messages": progress_messages,
        "error": error,
    }
