from sqlalchemy import JSON, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from know_engine_py.app.models.base import Base, BaseEntity


class ChatConversationModel(Base, BaseEntity):
    __tablename__ = "chat_conversation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    knowledge_base_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )


class ChatMessageModel(Base, BaseEntity):
    __tablename__ = "chat_message"
    __table_args__ = (
        Index("idx_chat_message_conversation_id", "conversation_id"),
        Index("idx_chat_message_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    transform_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rag_references: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    # SQLAlchemy 的 Base.metadata 是框架保留属性，所以 Python 属性名不能直接叫 metadata。
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
