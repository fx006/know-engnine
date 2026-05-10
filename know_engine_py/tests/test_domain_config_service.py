from sqlalchemy.ext.asyncio import AsyncEngine,create_async_engine,AsyncSession

from know_engine_py.app.db.session import create_session_maker_from_engine
from know_engine_py.app.models.base import Base
from know_engine_py.app.models.config import DomainConfigModel,IntentConfigModel
from know_engine_py.app.services.domain_config_service import DomainConfigService

async def create_test_tables(engine:AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def create_test_session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_test_tables(engine)
    return create_session_maker_from_engine(engine)

async def seed_automotive_domain(session:AsyncSession):
    """写入汽车领域和两个启用意图，用于领域配置服务测试。"""
    session.add_all(
        [
            DomainConfigModel(
                domain_id="automotive",
                name="汽车智能客服",
                fallback_intent="其他",
                is_active=1,
            ),
            DomainConfigModel(
                domain_id="inactive",
                name="停用领域",
                fallback_intent="其他",
                is_active=0,
            ),
            IntentConfigModel(
                domain_id="automotive",
                intent_name="其他",
                sort_order=99,
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
                intent_name="停用意图",
                sort_order=0,
                is_active=0,
            ),
        ]
    )
    await session.commit()



async def test_domain_config_service_returns_active_domain_and_sorted_intents():
    session_maker = await create_test_session_maker()

    async with session_maker() as session:
        await seed_automotive_domain(session)

        service = DomainConfigService(session)
        domain = await service.get_active_domain()
        intents = await service.list_active_intents(domain.domain_id)
        fallback = await service.get_intent_or_fallback(domain_id=domain.domain_id, intent_name="不存在的意图")

    assert domain.domain_id == "automotive"
    assert [intent.intent_name for intent in intents] == ["售前咨询与购买","其他"]
    assert fallback.intent_name == "其他"

async def test_domain_config_service_returns_matched_intent_before_fallback():
    session_maker=await create_test_session_maker()

    async with session_maker() as session:
        await seed_automotive_domain(session)

        service = DomainConfigService(session)
        intent = await service.get_intent_or_fallback(
            domain_id="automotive",
            intent_name="售前咨询与购买",
        )

    assert intent.intent_name == "售前咨询与购买"



