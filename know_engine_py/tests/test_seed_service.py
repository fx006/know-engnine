from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine,AsyncEngine

from know_engine_py.app.db.session import create_session_maker_from_engine
from know_engine_py.app.models.base import Base
from know_engine_py.app.models.config import (
    DomainConfigModel,
    IntentConfigModel,
    PromptTemplateModel,
)
from know_engine_py.app.services.seed_service import SeedService

async def create_test_tables(engine:AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def create_test_session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker=create_session_maker_from_engine(engine)
    await create_test_tables(engine)
    return session_maker

async def test_import_domain_package():
    session_maker = await create_test_session_maker()
    yaml_path = Path("know_engine_py/config/domains/automotive.yaml")

    async with session_maker() as session:
        service = SeedService(session)

        await service.import_domain_package(yaml_path)

        domain =(
            await session.execute(
                select(DomainConfigModel).where(
                    DomainConfigModel.domain_id=="automotive"
                )
            )
        ).scalar_one()

        intents = (
            await session.execute(
                select(IntentConfigModel)
                .where(IntentConfigModel.domain_id=="automotive")
                .order_by(IntentConfigModel.sort_order)
            )
        ).scalars().all()

        prompt = (
            await session.execute(
                select(PromptTemplateModel).where(
                    PromptTemplateModel.domain_id == "automotive",
                    PromptTemplateModel.intent_name == "售前咨询与购买",
                    PromptTemplateModel.prompt_type == "chat",
                )
            )
        ).scalar_one()

        intent_recognition_prompt = (
            await session.execute(
                select(PromptTemplateModel).where(
                    PromptTemplateModel.domain_id == "automotive",
                    PromptTemplateModel.intent_name == "_system_",
                    PromptTemplateModel.prompt_type == "intent_recognition",
                )
            )
        ).scalar_one()

    assert domain.name == "汽车智能客服"
    assert domain.entity_schema["car_model"] == "车型，如 Model 3、A6L。"

    assert [intent.intent_name for intent in intents] == [
        "售前咨询与购买",
        "售后维修与保养",
        "车辆使用与技术指导",
        "投诉与维权",
        "汽车营销政策",
        "其他",
    ]

    assert "你是一位汽车售前咨询助手" in prompt.content
    assert "{{userMessage}}" in prompt.content
    assert "{{intent_taxonomy}}" in intent_recognition_prompt.content
    assert "{{entity_schema}}" in intent_recognition_prompt.content
