from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.documents import Document


class AgentState(TypedDict, total=False):
    """LangGraph RAG 状态。

    这个状态贯穿 intent、transform、router、retrieve、generate 等节点。
    Day6 只使用基础字段，但提前预留 Day7 Corrective RAG 和 Day8 SSE/引用字段，
    避免后面为了加流式输出和引用溯源大改状态结构。
    """

    query: str
    user_id: str
    domain_id: str
    group_id: str | None
    knowledge_base_id: str | None

    conversation_id: str | None
    message_id: str | None
    assistant_message_id: str | None
    chat_history: list[dict[str, str]]

    is_related: bool
    intent_result: dict[str, Any] | None

    needs_clarification: bool
    clarification_events: list[dict[str, Any]]

    transformed_query: str | None
    route_strategy: str | None
    route_plan: list[dict[str, Any]]
    route_planner_source: str | None
    route_planner_error: str | None

    retrieved_docs: list[Document]
    selected_docs: list[Document]

    grade_result: dict[str, Any] | None
    needs_rewrite: bool
    evidence_warning: dict[str, Any] | None

    system_prompt: str | None
    response: str | None

    progress_messages: list[str]
    rag_references: list[dict[str, Any]]

    retry_count: int
    max_retries: int
    error: str | None


def build_initial_state(
    query: str,
    user_id: str,
    *,
    domain_id: str = "automotive",
    group_id: str | None = None,
    knowledge_base_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    assistant_message_id: str | None = None,
    chat_history: list[dict[str, str]] | None = None,
    max_retries: int = 2,
) -> AgentState:
    """构造 LangGraph 初始状态。"""
    return {
        "query": query,
        "user_id": user_id,
        "domain_id": domain_id,
        "group_id": group_id,
        "knowledge_base_id": knowledge_base_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "assistant_message_id": assistant_message_id,
        "chat_history": chat_history or [],
        "is_related": False,
        "intent_result": None,
        "needs_clarification": False,
        "clarification_events": [],
        "transformed_query": None,
        "route_strategy": None,
        "route_plan": [],
        "route_planner_source": None,
        "route_planner_error": None,
        "retrieved_docs": [],
        "selected_docs": [],
        "grade_result": None,
        "needs_rewrite": False,
        "evidence_warning": None,
        "system_prompt": None,
        "response": None,
        "progress_messages": [],
        "rag_references": [],
        "retry_count": 0,
        "max_retries": max_retries,
        "error": None,
    }
