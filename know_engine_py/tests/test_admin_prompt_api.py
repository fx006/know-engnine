from httpx import ASGITransport,AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine,create_async_engine

from know_engine_py.app.db.session import create_session_maker_from_engine,get_db
from know_engine_py.app.models.config import PromptTemplateModel
from know_engine_py.app.models.base import Base
from know_engine_py.app.main import app

async def create_test_tables(engine:AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_test_session_maker():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_test_tables(engine)
    return create_session_maker_from_engine(engine)

async def seed_prompts(session_maker)->None:
    async with session_maker() as session:
        session.add_all(
            [
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
                    intent_name="售前咨询与购买",
                    prompt_type="chat",
                    content="你是新一代汽车销售顾问。",
                    version=2,
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

async def test_admin_list_prompts_filters_by_intent_and_orders_by_version_desc():
    session_maker=await create_test_session_maker()
    await seed_prompts(session_maker)

    async def override_get_db():
        async with session_maker() as session:
            yield session
    app.dependency_overrides[get_db]=override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response=await client.get(
                "/admin/domains/automotive/prompts",
                params={"intent_name": "售前咨询与购买"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code==200
    data=response.json()

    assert [item["version"] for item in data] == [2, 1]
    assert all(item["intent_name"] == "售前咨询与购买" for item in data)
    assert data[0]["content"] == "你是新一代汽车销售顾问。"
