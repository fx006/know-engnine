from __future__ import annotations

from collections.abc import Awaitable, Callable

from langgraph.graph import END, StateGraph

from know_engine_py.app.rag.state import AgentState

GraphNode = Callable[[AgentState], Awaitable[AgentState]]


def build_rag_graph(
    *,
    intent_node: GraphNode,
    clarify_node: GraphNode,
    common_chat_node: GraphNode,
    transform_node: GraphNode,
    router_node: GraphNode,
    retrieve_node: GraphNode,
    generator_node: GraphNode,
):
    """组装 Day6 基础 RAG 状态图。

    这里只负责 LangGraph 拓扑，具体节点通过参数注入，避免 graph.py 直接依赖
    数据库 session、PromptService 或具体中间件客户端。
    """
    builder = StateGraph(AgentState)

    builder.add_node("intent", intent_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("common_chat", common_chat_node)
    builder.add_node("transform", transform_node)
    builder.add_node("router", router_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generator", generator_node)

    builder.set_entry_point("intent")

    builder.add_conditional_edges(
        "intent",
        _route_after_intent,
        {
            "common_chat": "common_chat",
            "clarify": "clarify",
        },
    )

    builder.add_conditional_edges(
        "clarify",
        _route_after_clarify,
        {
            "end": END,
            "transform": "transform",
        },
    )

    builder.add_edge("common_chat", END)
    builder.add_edge("transform", "router")
    builder.add_edge("router", "retrieve")
    builder.add_edge("retrieve", "generator")
    builder.add_edge("generator", END)

    return builder.compile()


def _route_after_intent(state: AgentState) -> str:
    if state.get("is_related"):
        return "clarify"
    return "common_chat"


def _route_after_clarify(state: AgentState) -> str:
    if state.get("needs_clarification") or state.get("error"):
        return "end"
    return "transform"
