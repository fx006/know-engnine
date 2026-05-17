from __future__ import annotations

from collections.abc import Mapping, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage


def build_chat_messages(
    *,
    system_prompt: str,
    chat_history: Sequence[Mapping[str, str]] | None,
    current_user_message: str,
) -> list[BaseMessage]:
    """构造 LangChain ChatModel 消息列表。

    Java 版通过 ChatMemoryStore 隐式注入历史消息；Python 版在 LangGraph state
    中显式保存 chat_history，再在节点调用模型前转成 LangChain Message。
    """
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    messages.extend(history_to_messages(chat_history))
    messages.append(HumanMessage(content=current_user_message))
    return messages


def history_to_messages(
    chat_history: Sequence[Mapping[str, str]] | None,
) -> list[BaseMessage]:
    """把 state 中的历史消息字典转成 LangChain Message。"""
    messages: list[BaseMessage] = []

    for item in chat_history or []:
        role = str(item.get("role") or "").lower()
        content = str(item.get("content") or "").strip()

        if not content:
            continue

        if role in {"user", "human"}:
            messages.append(HumanMessage(content=content))
        elif role in {"assistant", "ai"}:
            messages.append(AIMessage(content=content))

    return messages
