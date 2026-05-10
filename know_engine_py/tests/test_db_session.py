from sqlalchemy import text

from know_engine_py.app.core.settings import get_settings
from know_engine_py.app.db.session import (
    create_session_maker,
    get_session_maker,
    reset_session_maker_cache,
)


async def test_async_session_can_execute_sql():
    session_maker = create_session_maker("sqlite+aiosqlite:///:memory:")

    async with session_maker() as session:

        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


def test_session_maker_reads_database_url_from_settings_lazily(monkeypatch):
    get_settings.cache_clear()
    reset_session_maker_cache()

    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./lazy_test.db")

    session_maker = get_session_maker()

    assert str(session_maker.kw["bind"].url) == "sqlite+aiosqlite:///./lazy_test.db"

    reset_session_maker_cache()
    get_settings.cache_clear()