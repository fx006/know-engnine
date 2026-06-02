from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatSendRequest(BaseModel):
    """发送聊天消息请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str | None = Field(default=None, alias="userId")
    content: str
    conversation_id: str | None = Field(default=None, alias="conversationId")
    knowledge_base_id: str | None = Field(default=None, alias="knowledgeBaseId")



class ChatConversationResponse(BaseModel):
    """聊天会话响应模型，对应 chat_conversation 表的前端可见字段。"""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    user_id: str
    group_id: str | None = None
    knowledge_base_id: str | None = None
    title: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    """聊天消息响应模型，对应 chat_message 表的前端可见字段。"""

    model_config = ConfigDict(from_attributes=True)

    message_id: str
    conversation_id: str
    type: str
    content: str | None = None
    transform_content: str | None = None
    token_count: int | None = None
    model_name: str | None = None
    rag_references: list[dict[str, Any]] | None = None
    extra_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
