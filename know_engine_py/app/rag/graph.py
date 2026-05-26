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
    route_executor_node: GraphNode,
    reranker_node: GraphNode,
    grader_node: GraphNode,
    rewrite_node: GraphNode,
    reference_node: GraphNode,
    generator_node: GraphNode,
):
    """组装 Corrective RAG 状态图。

    这里只负责 LangGraph 拓扑和条件边，具体节点通过参数注入，
    避免 graph.py 直接依赖数据库 session、PromptService 或具体中间件客户端。
    """
    builder = StateGraph(AgentState)

    builder.add_node("intent", intent_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("common_chat", common_chat_node)
    builder.add_node("transform", transform_node)
    builder.add_node("router", router_node)
    builder.add_node("route_executor", route_executor_node)
    builder.add_node("reranker", reranker_node)
    builder.add_node("grader", grader_node)
    builder.add_node("reference", reference_node)
    builder.add_node("rewrite", rewrite_node)
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

    builder.add_conditional_edges(
        "grader",
        _route_after_grader,
        {
            "reference": "reference",
            "rewrite": "rewrite",
        },
    )

    builder.add_edge("common_chat", END)
    builder.add_edge("transform", "router")
    builder.add_edge("router", "route_executor")
    builder.add_edge("route_executor", "reranker")
    builder.add_edge("reranker", "grader")
    builder.add_edge("rewrite", "router")
    builder.add_edge("reference", "generator")
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


def _route_after_grader(state: AgentState) -> str:
    """根据检索评估结果决定是否进入 rewrite 循环。"""
    if not state.get("needs_rewrite"):
        return "reference"

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 0)
    if retry_count >= max_retries:
        return "reference"

    return "rewrite"
