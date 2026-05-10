from httpx import ASGITransport,AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine,create_async_engine,async_sessionmaker,AsyncSession

from know_engine_py.app.db.session import create_session_maker_from_engine,get_db
from know_engine_py.app.main import app
from know_engine_py.app.models.base import Base
from know_engine_py.app.models.config import DomainConfigModel

async def create_test_tables(engine:AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def create_test_session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_test_tables(engine)
    return create_session_maker_from_engine(engine)

async def seed_domains(session_maker:async_sessionmaker[AsyncSession]) ->None:
    async with session_maker() as session:
        session.add_all(
            [
                DomainConfigModel(
                    domain_id="automotive",
                    name="汽车智能客服",
                    description="汽车领域知识库",
                    entity_schema={"car_model":"车型"},
                    fallback_intent="其他",
                    is_active=1,
                ),
                DomainConfigModel(
                    domain_id="medical",
                    name="医疗智能客服",
                    description="医疗领域知识库",
                    fallback_intent="其他",
                    is_active=0,
                ),
            ]
        )
        await session.commit()

async def test_admin_list_domains_returns_all_domains():
    session_maker = await create_test_session_maker()
    await seed_domains(session_maker)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db]=override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/admin/domains")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code==200
    data=response.json()

    assert len(data) == 2
    assert data[0]["domain_id"] == "automotive"
    assert data[0]["name"] == "汽车智能客服"
    assert data[0]["entity_schema"]["car_model"] == "车型"


async def test_admin_get_domain_returns_domain_detail():
    session_maker = await create_test_session_maker()
    await seed_domains(session_maker)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db]=override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/admin/domains/automotive")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()

    assert data["domain_id"] == "automotive"
    assert data["fallback_intent"] == "其他"
    assert data["is_active"] == 1
