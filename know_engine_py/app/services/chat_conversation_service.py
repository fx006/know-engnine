from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models.chat import ChatConversationModel
from know_engine_py.app.models.enums import ChatConversationStatus
from know_engine_py.app.services.chat_title_service import ChatTitleService


class ChatConversationService:
    """聊天会话业务服务。

    负责创建、查询和维护会话状态。该服务只做 flush，不主动 commit，
    事务边界由 API 层或上层应用服务控制。
    """

    def __init__(
            self,
            session: AsyncSession,
            title_service:ChatTitleService|None=None):
        self.session = session
        self.title_service = title_service or ChatTitleService()

    async def create_conversation(
        self,
        *,
        user_id: str,
        title: str | None = None,
    ) -> ChatConversationModel:
        """创建新会话，并返回会话模型。"""
        if not user_id or not user_id.strip():
            raise ValueError("user_id 不能为空")

        conversation = ChatConversationModel(
            conversation_id=uuid4().hex,
            user_id=user_id.strip(),
            title=self.title_service.normalize_title(title),
            status=ChatConversationStatus.ACTIVE.value,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def ensure_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        first_message: str,
    ) -> ChatConversationModel:
        """确保本轮聊天有可用会话。

        - conversation_id 为空：按用户首句创建新会话。
        - conversation_id 不为空：校验会话存在、未删除、且属于当前用户。
        """
        if not conversation_id or not conversation_id.strip():
            return await self.create_conversation(
                user_id=user_id,
                title=self.title_service.build_temporary_title(first_message),
            )

        conversation = await self.get_by_conversation_id(conversation_id)
        if conversation is None:
            raise ValueError("会话不存在或已删除")

        if conversation.user_id != user_id:
            raise ValueError("会话不属于当前用户")

        return conversation

    async def get_by_conversation_id(
        self,
        conversation_id: str,
        *,
        include_deleted: bool = False,
    ) -> ChatConversationModel | None:
        """按 conversation_id 查询会话。默认不返回已删除会话。"""
        stmt = select(ChatConversationModel).where(
            ChatConversationModel.conversation_id == conversation_id
        )

        if not include_deleted:
            stmt = stmt.where(
                ChatConversationModel.status != ChatConversationStatus.DELETED.value
            )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_conversations(self, user_id: str) -> list[ChatConversationModel]:
        """查询用户会话列表，排除已删除会话，按更新时间倒序。"""
        result = await self.session.execute(
            select(ChatConversationModel)
            .where(ChatConversationModel.user_id == user_id)
            .where(ChatConversationModel.status != ChatConversationStatus.DELETED.value)
            .order_by(
                ChatConversationModel.updated_at.desc(),
                ChatConversationModel.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def update_title(
        self,
        conversation_id: str,
        title: str,
    ) -> ChatConversationModel:
        """更新会话标题。"""
        conversation = await self._get_existing_conversation_or_raise(conversation_id)
        conversation.title = self.title_service.normalize_title(title)
        await self.session.flush()
        return conversation

    async def archive_conversation(self, conversation_id: str) -> ChatConversationModel:
        """归档会话。"""
        conversation = await self._get_existing_conversation_or_raise(conversation_id)
        conversation.status = ChatConversationStatus.ARCHIVED.value
        await self.session.flush()
        return conversation

    async def delete_conversation(self, conversation_id: str) -> ChatConversationModel:
        """软删除会话。"""
        conversation = await self._get_existing_conversation_or_raise(conversation_id)
        conversation.status = ChatConversationStatus.DELETED.value
        await self.session.flush()
        return conversation

    async def _get_existing_conversation_or_raise(
        self,
        conversation_id: str,
    ) -> ChatConversationModel:
        conversation = await self.get_by_conversation_id(conversation_id)
        if conversation is None:
            raise ValueError("会话不存在或已删除")
        return conversation
