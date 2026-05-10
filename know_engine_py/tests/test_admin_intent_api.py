from httpx import AsyncClient,ASGITransport
from sqlalchemy.ext.asyncio import AsyncEngine,create_async_engine

from know_engine_py.app.db.session import create_session_maker_from_engine,get_db
from know_engine_py.app.main import app
from know_engine_py.app.models.base import Base
from know_engine_py.app.models.config import DomainConfigModel,IntentConfigModel

async def create_test_tables(engine:AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def create_test_session_maker():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_test_tables(engine)
    return create_session_maker_from_engine(engine)

async def seed_domain_and_intents(session_maker)->None:
    async with session_maker() as session:
        session.add(
            DomainConfigModel(
                domain_id="automotive",
                name="汽车智能客服",
                fallback_intent="其他",
                is_active=1
            )
        )
        session.add_all(
            [
                IntentConfigModel(
                    domain_id="automotive",
                    intent_name="售前咨询与购买",
                    intent_description="车型、价格、配置咨询",
                    retrieval_strategy="hybrid",
                    data_sources='["milvus","es"]',
                    sort_order=1,
                    is_active=1,
                ),
                IntentConfigModel(
                    domain_id="automotive",
                    intent_name="其他",
                    intent_description="无法归类的汽车问题",
                    retrieval_strategy="hybrid",
                    data_sources='["milvus","es"]',
                    sort_order=99,
                    is_active=1,
                ),
            ]
        )
        await session.commit()

async def test_admin_list_intents_by_domain_returns_sorted_intents():
    session_maker=await create_test_session_maker()
    await seed_domain_and_intents(session_maker)

    async def override_get_db():
        async with session_maker() as session:
            yield session
    app.dependency_overrides[get_db]=override_get_db

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/admin/domains/automotive/intents")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code==200
    data=response.json()

    assert [item["intent_name"] for item in data] == [
        "售前咨询与购买",
        "其他",
    ]
    assert data[0]["retrieval_strategy"] == "hybrid"
    assert data[0]["data_sources"] == '["milvus","es"]'
