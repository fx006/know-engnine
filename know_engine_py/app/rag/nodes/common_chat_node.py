from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from know_engine_py.app.rag.nodes.message_history import build_chat_messages

from know_engine_py.app.rag.state import AgentState


class CommonChatPromptService(Protocol):
    """common_chat_node 只依赖 PromptService 的指定 Prompt 查询能力。"""

    async def get_prompt(
        self,
        domain_id: str,
        intent_name: str,
        prompt_type: str,
    ) -> str | None:
        ...


CommonChatNode = Callable[[AgentState], Awaitable[AgentState]]


def create_common_chat_node(
    prompt_service: CommonChatPromptService,
    chat_model: BaseChatModel,
) -> CommonChatNode:
    """创建通用聊天节点。

    当 intent_node 判断用户问题不属于当前业务领域时，
    该节点直接调用普通 LLM 生成回答，不进入 RAG 检索链路。
    """

    async def common_chat_node(state: AgentState) -> AgentState:
        progress_messages = [
            *state.get("progress_messages", []),
            "[PROGRESS]:正在为您生成回答...",
        ]

        prompt = await prompt_service.get_prompt(
            domain_id=state.get("domain_id", "automotive"),
            intent_name="_system_",
            prompt_type="common_chat",
        )

        if not prompt:
            return {
                **state,
                "progress_messages": progress_messages,
                "response": None,
                "error": "缺少 common_chat Prompt",
            }

        response = await chat_model.ainvoke(
            build_chat_messages(
                system_prompt=prompt,
                chat_history=state.get("chat_history"),
                current_user_message=state["query"],
            )
        )

        return {
            **state,
            "response": response.content.strip(),
            "progress_messages": progress_messages,
            "error": None,
        }

    return common_chat_node
