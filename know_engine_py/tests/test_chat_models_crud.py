from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from know_engine_py.app.db.session import create_session_maker_from_engine
from know_engine_py.app.models.base import Base
from know_engine_py.app.models.chat import ChatConversationModel, ChatMessageModel


async def create_test_tables(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_chat_models_can_be_inserted_and_queried():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = create_session_maker_from_engine(engine)

    await create_test_tables(engine)

    async with session_maker() as session:
        conversation = ChatConversationModel(
            conversation_id="conv-001",
            user_id="user-001",
            title="新对话",
        )
        user_message = ChatMessageModel(
            message_id="msg-001",
            conversation_id="conv-001",
            type="USER",
            content="帮我介绍一下比亚迪汉",
        )
        assistant_message = ChatMessageModel(
            message_id="msg-002",
            conversation_id="conv-001",
            type="ASSISTANT",
            content="比亚迪汉是一款中大型新能源轿车。",
            model_name="qwen-plus",
            token_count=128,
            rag_references=[
                {
                    "document_id": "doc-001",
                    "document_title": "车型手册",
                    "chunk_id": "chunk-001",
                    "retrieval_source": "hybrid",
                    "similarity_score": 0.91,
                }
            ],
            extra_metadata={"latency_ms": 350},
        )

        session.add_all([conversation, user_message, assistant_message])
        await session.commit()

    async with session_maker() as session:
        conversation = (
            await session.execute(
                select(ChatConversationModel).where(
                    ChatConversationModel.conversation_id == "conv-001"
                )
            )
        ).scalar_one()

        messages = (
            await session.execute(
                select(ChatMessageModel)
                .where(ChatMessageModel.conversation_id == "conv-001")
                .order_by(ChatMessageModel.id)
            )
        ).scalars().all()

    assert conversation.user_id == "user-001"
    assert conversation.status == "active"

    assert len(messages) == 2
    assert messages[0].type == "USER"
    assert messages[1].model_name == "qwen-plus"
    assert messages[1].rag_references[0]["document_title"] == "车型手册"
    assert messages[1].extra_metadata["latency_ms"] == 350
