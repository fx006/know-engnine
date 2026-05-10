from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from know_engine_py.app.db.session import create_session_maker_from_engine
from know_engine_py.app.models.base import Base
from know_engine_py.app.services.domain_config_service import DomainConfigService
from know_engine_py.app.services.prompt_service import PromptService
from know_engine_py.app.services.seed_service import SeedService


async def create_test_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_test_session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_test_tables(engine)
    return create_session_maker_from_engine(engine)


async def test_seeded_template_intent_prompt_is_rendered_from_domain_config():
    session_maker = await create_test_session_maker()
    yaml_path = Path("know_engine_py/config/domains/automotive.yaml")

    async with session_maker() as session:
        seed_service = SeedService(session)
        await seed_service.import_domain_package(yaml_path)

        domain_config_service = DomainConfigService(session)
        prompt_service = PromptService(session, domain_config_service)

        prompt = await prompt_service.build_intent_recognition_prompt()

    assert "你是汽车智能客服意图识别助手" in prompt
    assert "# Intent Taxonomy" in prompt
    assert "## 意图类别" in prompt
    assert "售前咨询与购买" in prompt
    assert "售后维修与保养" in prompt
    assert "## 需要抽取的实体" in prompt
    assert "car_model: 车型，如 Model 3、A6L。" in prompt
