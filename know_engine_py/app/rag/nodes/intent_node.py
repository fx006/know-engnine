from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from know_engine_py.app.rag.nodes.message_history import build_chat_messages

from know_engine_py.app.rag.state import AgentState


class IntentPromptService(Protocol):
    """intent_node 只依赖 PromptService 的意图识别 Prompt 构建能力。"""

    async def build_intent_recognition_prompt(self) -> str:
        ...

    async def list_entity_fields(self) -> list[str]:
        ...

IntentNode = Callable[[AgentState], Awaitable[AgentState]]


def create_intent_node(
    prompt_service: IntentPromptService,
    chat_model: BaseChatModel,
) -> IntentNode:
    """创建意图识别节点。

    节点职责：
    1. 从 PromptService 获取动态意图识别 Prompt。
    2. 调用 LangChain ChatModel。
    3. 解析 LLM 返回的 JSON。
    4. 写回 is_related 和 intent_result。
    """

    async def intent_node(state: AgentState) -> AgentState:
        progress_messages = [
            *state.get("progress_messages", []),
            "[PROGRESS]:正在识别您的意图...",
        ]

        system_prompt = await prompt_service.build_intent_recognition_prompt()
        response = await chat_model.ainvoke(
            build_chat_messages(
                system_prompt=system_prompt,
                chat_history=state.get("chat_history"),
                current_user_message=state["query"],
            )
        )

        try:
            entity_fields = await prompt_service.list_entity_fields()
            intent_result = _parse_intent_result(
                response.content,
                entity_fields=entity_fields,
            )
        except ValueError as exc:
            return {
                **state,
                "is_related": False,
                "intent_result": None,
                "progress_messages": progress_messages,
                "error": str(exc),
            }

        return {
            **state,
            "is_related": bool(intent_result.get("related", False)),
            "intent_result": intent_result,
            "progress_messages": progress_messages,
            "error": None,
        }

    return intent_node


def _parse_intent_result(
    content: str,
    *,
    entity_fields: list[str] | None = None,
) -> dict:
    """解析意图识别 JSON，并补齐后续节点依赖的基础字段。"""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("意图识别结果不是合法 JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("意图识别结果必须是 JSON 对象")

    data.setdefault("related", False)
    data.setdefault("intent", "")
    data.setdefault("reasoning", "")

    entities = data.get("entities")
    if not isinstance(entities, dict):
        entities = {}

    normalized_entities = {
        field: entities.get(field)
        for field in (entity_fields or [])
    }

    # 保留 LLM 额外抽取到但暂未配置的字段，便于观察和后续扩展。
    for field, value in entities.items():
        normalized_entities.setdefault(field, value)

    data["entities"] = normalized_entities
    return data
