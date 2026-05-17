from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from know_engine_py.app.rag.nodes.message_history import build_chat_messages

from know_engine_py.app.rag.state import AgentState


class TransformPromptService(Protocol):
    """transform_node 只依赖 PromptService 的指定 Prompt 查询能力。"""

    async def get_prompt(
        self,
        domain_id: str,
        intent_name: str,
        prompt_type: str,
    ) -> str | None:
        ...


TransformNode = Callable[[AgentState], Awaitable[AgentState]]


def create_transform_node(
    prompt_service: TransformPromptService,
    chat_model: BaseChatModel,
) -> TransformNode:
    """创建查询改写节点。"""

    async def transform_node(state: AgentState) -> AgentState:
        progress_messages = [
            *state.get("progress_messages", []),
            "[PROGRESS]:正在优化您的问题...",
        ]

        prompt = await prompt_service.get_prompt(
            domain_id=state.get("domain_id", "automotive"),
            intent_name="_system_",
            prompt_type="query_transform",
        )

        if not prompt:
            return {
                **state,
                "progress_messages": progress_messages,
                "error": "缺少 query_transform Prompt",
            }

        response = await chat_model.ainvoke(
            build_chat_messages(
                system_prompt=prompt,
                chat_history=state.get("chat_history"),
                current_user_message=state["query"],
            )
        )

        rewritten_query = response.content.strip() or state["query"]
        enhanced_query = _build_enhanced_query(
            rewritten_query=rewritten_query,
            user_id=state["user_id"],
        )

        return {
            **state,
            "transformed_query": enhanced_query,
            "progress_messages": progress_messages,
            "error": None,
        }

    return transform_node


def _build_enhanced_query(rewritten_query: str, user_id: str) -> str:
    """构造给检索器使用的增强查询。

    保留 Java 版“我的问题是 + 用户 ID + 当前时间”的意图，
    但先只作为字符串进入 retriever，不在这里写数据库。
    """
    return f"我的问题是：{rewritten_query}, 我的用户Id是: {user_id}, 现在是：{datetime.now()}"
