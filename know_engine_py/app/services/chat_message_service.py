from __future__ import annotations

from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models.chat import ChatMessageModel
from know_engine_py.app.models.enums import ChatMessageType


class ChatMessageService:
    """聊天消息业务服务。

    负责用户消息、assistant 占位消息、改写内容、RAG 引用和最终回答的落库。
    该服务只 flush，不 commit；事务边界交给上层 ChatApplicationService 或 API 层。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_user_message(
        self,
        *,
        conversation_id: str,
        content: str,
    ) -> ChatMessageModel:
        """保存用户原始问题。"""
        message = ChatMessageModel(
            message_id=uuid4().hex,
            conversation_id=conversation_id,
            type=ChatMessageType.USER.value,
            content=content,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def save_assistant_message(
        self,
        *,
        conversation_id: str,
    ) -> ChatMessageModel:
        """预创建 assistant 消息，后续流式完成后再回写 content。"""
        message = ChatMessageModel(
            message_id=uuid4().hex,
            conversation_id=conversation_id,
            type=ChatMessageType.ASSISTANT.value,
            content=None,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def get_by_message_id(self, message_id: str) -> ChatMessageModel | None:
        """按 message_id 查询消息。"""
        result = await self.session.execute(
            select(ChatMessageModel).where(ChatMessageModel.message_id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_messages_by_conversation_id(
        self,
        conversation_id: str,
    ) -> list[ChatMessageModel]:
        """查询会话全部消息，按写入顺序正序返回。"""
        result = await self.session.execute(
            select(ChatMessageModel)
            .where(ChatMessageModel.conversation_id == conversation_id)
            .order_by(ChatMessageModel.id.asc())
        )
        return list(result.scalars().all())

    async def update_transform_content(
        self,
        message_id: str,
        transform_content: str,
    ) -> ChatMessageModel:
        """回写用户问题改写结果。"""
        message = await self._get_message_or_raise(
            message_id,
            expected_type=ChatMessageType.USER
        )
        message.transform_content = transform_content
        await self.session.flush()
        return message

    async def update_rag_references(
        self,
        message_id: str,
        rag_references: list[dict],
    ) -> ChatMessageModel:
        """回写 assistant 消息引用资料。"""
        message = await self._get_message_or_raise(
            message_id,
            expected_type=ChatMessageType.ASSISTANT,
        )
        message.rag_references = rag_references
        await self.session.flush()
        return message

    async def update_content(
        self,
        message_id: str,
        content: str,
        *,
        model_name: str | None = None,
        token_count: int | None = None,
    ) -> ChatMessageModel:
        """回写 assistant 最终回答内容。"""
        message = await self._get_message_or_raise(
            message_id,
            expected_type=ChatMessageType.ASSISTANT,
        )
        message.content = content
        if model_name is not None:
            message.model_name = model_name
        if token_count is not None:
            message.token_count = token_count

        await self.session.flush()
        return message

    async def get_recent_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
        exclude_latest_count: int = 2,
    ) -> list[ChatMessageModel]:
        """查询最近历史消息。

        Java 版会排除最新两条，因为当前轮会先保存 user 消息和空 assistant 消息。
        这里保留同样语义，返回结果再反转为时间正序，方便后续转 LangChain history。
        """
        result = await self.session.execute(
            select(ChatMessageModel)
            .where(ChatMessageModel.conversation_id == conversation_id)
            .order_by(ChatMessageModel.id.desc())
            .limit(limit + exclude_latest_count)
        )
        records = list(result.scalars().all())

        if len(records) <= exclude_latest_count:
            return []

        history = records[exclude_latest_count:]
        history.reverse()
        return history

    async def delete_messages_by_conversation_id(self, conversation_id: str) -> int:
        """删除指定会话下的所有消息，返回删除数量。"""
        result = await self.session.execute(
            delete(ChatMessageModel).where(
                ChatMessageModel.conversation_id == conversation_id
            )
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    async def _get_message_or_raise(
            self,
            message_id: str,
            *,
            expected_type: ChatMessageType|None=None
    ) -> ChatMessageModel:
        message = await self.get_by_message_id(message_id)
        if message is None:
            raise ValueError("消息不存在")

        if expected_type is not None and message.type!=expected_type.value:
            raise ValueError(f"消息类型错误，期望 {expected_type.value}，实际 {message.type}")

        return message