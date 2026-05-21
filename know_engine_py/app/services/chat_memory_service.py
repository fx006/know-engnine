from __future__ import annotations

from typing import Protocol

from know_engine_py.app.models.chat import ChatMessageModel
from know_engine_py.app.models.enums import ChatMessageType
from know_engine_py.app.services.chat_message_service import ChatMessageService


class ChatMemoryCache(Protocol):
    """聊天记忆缓存协议。

    后续 Redis adapter 实现这个协议；当前服务不直接依赖 Redis SDK。
    """

    async def get(self, key: str) -> list[dict[str, str]] | None:
        ...

    async def set(self, key: str, value: list[dict[str, str]]) -> None:
        ...

    async def delete(self, key: str) -> None:
        ...


class ChatMemoryService:
    """聊天短期记忆服务。

    负责把 chat_message 表里的最近消息转成 LangGraph AgentState.chat_history。
    当前只处理短期窗口记忆；摘要记忆和长期事实记忆后续单独扩展。
    """

    def __init__(
        self,
        message_service: ChatMessageService,
        *,
        cache: ChatMemoryCache | None = None,
        max_messages: int = 10,
    ):
        if max_messages <= 0:
            raise ValueError("max_messages 必须大于 0")

        self.message_service = message_service
        self.cache = cache
        self.max_messages = max_messages

    async def load_recent_chat_history(
        self,
        conversation_id: str,
        *,
        exclude_latest_count: int = 2,
    ) -> list[dict[str, str]]:
        """加载最近窗口聊天历史。

        默认排除当前轮刚保存的 user 消息和空 assistant 消息。
        返回值直接进入 AgentState.chat_history。
        """
        cache_key = self._build_cache_key(conversation_id, exclude_latest_count)

        cached = await self._get_cached_history(cache_key)
        if cached is not None:
            return cached

        messages = await self.message_service.get_recent_messages(
            conversation_id,
            limit=self.max_messages,
            exclude_latest_count=exclude_latest_count,
        )
        chat_history = self._to_chat_history(messages)

        await self._set_cached_history(cache_key, chat_history)
        return chat_history

    async def evict_cache(
        self,
        conversation_id: str,
        *,
        exclude_latest_count: int = 2,
    ) -> None:
        """清除指定会话的短期记忆缓存。"""
        cache_key = self._build_cache_key(conversation_id, exclude_latest_count)
        await self._delete_cached_history(cache_key)

    def _to_chat_history(
        self,
        messages: list[ChatMessageModel],
    ) -> list[dict[str, str]]:
        chat_history: list[dict[str, str]] = []

        for message in messages:
            item = self._to_history_item(message)
            if item is not None:
                chat_history.append(item)

        return chat_history

    def _to_history_item(
        self,
        message: ChatMessageModel,
    ) -> dict[str, str] | None:
        content = (message.content or "").strip()
        if not content:
            return None

        if message.type == ChatMessageType.USER.value:
            return {"role": "user", "content": content}

        if message.type == ChatMessageType.ASSISTANT.value:
            return {"role": "assistant", "content": content}

        return None

    async def _get_cached_history(
        self,
        key: str,
    ) -> list[dict[str, str]] | None:
        if self.cache is None:
            return None

        try:
            return await self.cache.get(key)
        except Exception:
            # 缓存只是加速层，失败时必须降级 DB，不能影响聊天主链路。
            return None

    async def _set_cached_history(
        self,
        key: str,
        value: list[dict[str, str]],
    ) -> None:
        if self.cache is None:
            return

        try:
            await self.cache.set(key, value)
        except Exception:
            return

    async def _delete_cached_history(self, key: str) -> None:
        if self.cache is None:
            return

        try:
            await self.cache.delete(key)
        except Exception:
            return

    def _build_cache_key(
        self,
        conversation_id: str,
        exclude_latest_count: int,
    ) -> str:
        return (
            f"know-engine:chat-memory:{conversation_id}:"
            f"limit:{self.max_messages}:exclude:{exclude_latest_count}"
        )