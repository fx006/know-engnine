from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncEngine,AsyncSession,create_async_engine

from know_engine_py.app.db.session import create_session_maker_from_engine
from know_engine_py.app.models.base import Base
from know_engine_py.app.models.config import (
    DomainConfigModel,
    IntentConfigModel,
    PromptTemplateModel,
)
from know_engine_py.app.services.domain_config_service import DomainConfigService
from know_engine_py.app.services.prompt_service import PromptService


async def create_test_tables(engine:AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def create_test_session_maker():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_test_tables(engine)

    return create_session_maker_from_engine(engine)

async def seed_prompt_data(session: AsyncSession):
    """写入领域、意图和 Prompt 模板，用于 PromptService 测试。"""
    session.add_all(
        [
            DomainConfigModel(
                domain_id="automotive",
                name="汽车智能客服",
                fallback_intent="其他",
                is_active=1,
            ),
            IntentConfigModel(
                domain_id="automotive",
                intent_name="售前咨询与购买",
                sort_order=1,
                is_active=1,
            ),
            IntentConfigModel(
                domain_id="automotive",
                intent_name="其他",
                sort_order=99,
                is_active=1,
            ),
            PromptTemplateModel(
                domain_id="automotive",
                intent_name="售前咨询与购买",
                prompt_type="chat",
                content="你是一名汽车销售顾问。",
                version=1,
                is_active=1,
            ),
            PromptTemplateModel(
                domain_id="automotive",
                intent_name="其他",
                prompt_type="chat",
                content="你是一名汽车客服助手。",
                version=1,
                is_active=1,
            ),
        ]
    )
    await session.commit()

async def test_prompt_service_returns_matched_prompt():
    session_maker=await create_test_session_maker()

    async with session_maker() as session:
        await seed_prompt_data(session)

        domain_config_service = DomainConfigService(session)
        prompt_service = PromptService(session,domain_config_service)
        prompt = await prompt_service.get_prompt(
            domain_id="automotive",
            intent_name="售前咨询与购买",
            prompt_type="chat",
        )

    assert prompt == "你是一名汽车销售顾问。"



async def test_prompt_service_fallbacks_when_intent_prompt_missing():
    session_maker = await create_test_session_maker()

    async with session_maker() as session:
        await seed_prompt_data(session)

        domain_config_service = DomainConfigService(session)
        prompt_service = PromptService(session, domain_config_service)

        prompt = await prompt_service.get_prompt(
            domain_id="automotive",
            intent_name="不存在的意图",
            prompt_type="chat",
        )

    assert prompt == "你是一名汽车客服助手。"

async def test_prompt_service_returns_latest_active_prompt_version():
    session_maker=await create_test_session_maker()

    async with session_maker() as session:
        await seed_prompt_data(session)

        session.add(
            PromptTemplateModel(
                domain_id="automotive",
                intent_name="售前咨询与购买",
                prompt_type="chat",
                content="你是新一代汽车销售顾问。",
                version=2,
                is_active=1
            )
        )
        await session.commit()

        domain_config_service = DomainConfigService(session)
        prompt_service = PromptService(session,domain_config_service)

        prompt= await prompt_service.get_prompt(
            domain_id="automotive",
            intent_name="售前咨询与购买",
            prompt_type="chat"
        )
    assert prompt == "你是新一代汽车销售顾问。"

async def test_prompt_service_returns_full_intent_recognition_prompt_without_extra_append():
    session_maker=await create_test_session_maker()

    async with session_maker() as session:
        await seed_prompt_data(session)

        domain:DomainConfigModel = (
            await session.execute(
                select (DomainConfigModel)
                .where(DomainConfigModel.domain_id=="automotive")
            )
        ).scalar_one()
        domain.entity_schema = {
            "car_model":"用户提到的车型",
            "dealer":"经销商名称",
        }

        session.add(
            PromptTemplateModel(
                domain_id="automotive",
                intent_name="_system_",
                prompt_type="intent_recognition",
                content="你是汽车客服意图识别助手。",
                version=1,
                is_active=1,
            )
        )
        await session.commit()

        domain_config_service = DomainConfigService(session)
        prompt_service = PromptService(session, domain_config_service)

        prompt = await prompt_service.build_intent_recognition_prompt()

    assert prompt == "你是汽车客服意图识别助手。"

async def test_prompt_service_renders_intent_recognition_prompt_when_template_has_placeholders():
    session_maker=await create_test_session_maker()

    async with session_maker() as session:
        await seed_prompt_data(session)

        domain:DomainConfigModel = (
            await session.execute(
                select (DomainConfigModel)
                .where(DomainConfigModel.domain_id=="automotive")
            )
        ).scalar_one()
        domain.entity_schema = {
            "car_model":"用户提到的车型",
            "dealer":"经销商名称",
        }

        session.add(
            PromptTemplateModel(
                domain_id="automotive",
                intent_name="_system_",
                prompt_type="intent_recognition",
                content=(
                    "你是{{domain_name}}意图识别助手。\n\n"
                    "{{intent_taxonomy}}\n\n"
                    "{{entity_schema}}"
                ),
                version=1,
                is_active=1,
            )
        )
        await session.commit()

        domain_config_service = DomainConfigService(session)
        prompt_service = PromptService(session, domain_config_service)

        prompt = await prompt_service.build_intent_recognition_prompt()

    assert "你是汽车智能客服意图识别助手。" in prompt
    assert "## 意图类别" in prompt
    assert "售前咨询与购买" in prompt
    assert "其他" in prompt
    assert "## 需要抽取的实体" in prompt
    assert "car_model: 用户提到的车型" in prompt
    assert "dealer: 经销商名称" in prompt
