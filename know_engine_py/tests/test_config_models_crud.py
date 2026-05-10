from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine,AsyncEngine



from know_engine_py.app.db.session import create_session_maker,create_session_maker_from_engine
from know_engine_py.app.models.base import Base
from know_engine_py.app.models.config import (
   DomainConfigModel,
   IntentConfigModel,
    PromptTemplateModel
)

async def create_test_tables(engine:AsyncEngine):

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_config_models_can_be_inserted_and_queried():
    database_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(database_url)
    session_maker = create_session_maker_from_engine(engine)

    await create_test_tables(engine)

    async with session_maker() as session:
        domain = DomainConfigModel(
            domain_id="automotive",
            name="汽车智能客服",
            description="汽车领域知识库",
            entity_schema={
                "car_model":"汽车型号",
                "dealer":"经销商",
            },
        )
        intent = IntentConfigModel(
            domain_id="automotive",
            intent_name="售前咨询与购买",
            intent_description="购车前的车型、价格、配置咨询",
        )
        prompt = PromptTemplateModel(
            domain_id="automotive",
            intent_name="售前咨询与购买",
            prompt_type="chat",
            content="你是一名汽车销售顾问。",
        )

        session.add_all([domain,intent, prompt])
        await session.commit()

    async with session_maker() as session:
        domain = (
            await session.execute(
                select(DomainConfigModel).where(
                    DomainConfigModel.domain_id == "automotive"
                )
            )
        ).scalar_one()

        intent = (
            await session.execute(
                select(IntentConfigModel).where(
                    IntentConfigModel.intent_name == "售前咨询与购买"
                )
            )
        ).scalar_one()

        prompt = (
            await session.execute(
                select(PromptTemplateModel).where(
                    PromptTemplateModel.prompt_type == "chat"
                )
            )
        ).scalar_one()

    assert domain.name == "汽车智能客服"
    assert domain.entity_schema["car_model"] == "汽车型号"
    assert domain.fallback_intent == "其他"
    assert domain.is_active == 1

    assert intent.retrieval_strategy == "hybrid"
    assert intent.data_sources == '["milvus","es"]'
    assert intent.sort_order == 0
    assert intent.is_active == 1

    assert prompt.version == 1
    assert prompt.is_active == 1
    assert prompt.content == "你是一名汽车销售顾问。"