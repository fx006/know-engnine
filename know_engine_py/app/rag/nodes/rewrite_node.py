from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol

from langchain_core.language_models import BaseChatModel

from know_engine_py.app.rag.nodes.message_history import build_chat_messages
from know_engine_py.app.rag.state import AgentState


class RewritePromptService(Protocol):
    """rewrite_node 只依赖 PromptService 的指定 Prompt 查询能力。"""

    async def get_prompt(
        self,
        domain_id: str,
        intent_name: str,
        prompt_type: str,
    ) -> str | None:
        ...


RewriteNode = Callable[[AgentState], Awaitable[AgentState]]


def create_rewrite_node(
    prompt_service: RewritePromptService,
    chat_model: BaseChatModel,
) -> RewriteNode:
    """创建检索失败后的二次 query 改写节点。"""

    async def rewrite_node(state: AgentState) -> AgentState:
        progress_messages = [
            *state.get("progress_messages", []),
            "[PROGRESS]:正在重新组织检索问题...",
        ]

        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 0)

        if retry_count >= max_retries:
            return {
                **state,
                "needs_rewrite": False,
                "progress_messages": progress_messages,
                "error": None,
            }

        prompt = await prompt_service.get_prompt(
            domain_id=state.get("domain_id", "automotive"),
            intent_name="_system_",
            prompt_type="query_rewrite",
        )

        if not prompt:
            return {
                **state,
                "needs_rewrite": False,
                "progress_messages": progress_messages,
                "error": "缺少 query_rewrite Prompt",
            }

        response = await chat_model.ainvoke(
            build_chat_messages(
                system_prompt=prompt,
                chat_history=state.get("chat_history"),
                current_user_message=_build_user_message(state),
            )
        )

        rewritten_query = str(response.content).strip()
        if not rewritten_query:
            rewritten_query = state.get("transformed_query") or state["query"]

        enhanced_query = _build_enhanced_query(
            rewritten_query=rewritten_query,
            user_id=state["user_id"],
        )

        return {
            **state,
            "transformed_query": enhanced_query,
            "retrieved_docs": [],
            "selected_docs": [],
            "rag_references": [],
            "grade_result": None,
            "needs_rewrite": False,
            "retry_count": retry_count + 1,
            "progress_messages": progress_messages,
            "error": None,
        }

    return rewrite_node


def _build_user_message(state: AgentState) -> str:
    """把 grader 反馈组织成 rewrite LLM 的输入。"""
    grade_result = state.get("grade_result") or {}
    missing_aspects = grade_result.get("missing_aspects") or []

    if isinstance(missing_aspects, list):
        missing_aspects_text = "、".join(str(item) for item in missing_aspects)
    else:
        missing_aspects_text = str(missing_aspects)

    return (
        f"用户原问题：\n{state['query']}\n\n"
        f"上一轮检索 query：\n{state.get('transformed_query') or state['query']}\n\n"
        f"资料不足原因：\n{grade_result.get('reason') or '未提供'}\n\n"
        f"缺失信息点：\n{missing_aspects_text or '未提供'}\n\n"
        "请改写成一个更适合知识库检索的查询。只输出改写后的查询文本。"
    )


def _build_enhanced_query(rewritten_query: str, user_id: str) -> str:
    """构造给 retriever 使用的增强 query。

    这里暂时复用 transform_node 的增强格式，确保二次检索仍带上用户和时间上下文。
    后续可以抽成共享 helper，避免两边格式漂移。
    """
    return f"我的问题是：{rewritten_query}, 我的用户Id是: {user_id}, 现在是：{datetime.now()}"