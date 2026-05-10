import pytest
from sqlalchemy import text

from know_engine_py.app.core.settings import get_settings
from know_engine_py.app.db.session import create_session_maker


MYSQL_TEST_DATABASE_URL = get_settings().mysql_test_database_url


@pytest.mark.skipif(
    not MYSQL_TEST_DATABASE_URL,
    reason="MYSQL_TEST_DATABASE_URL is not set; skip remote MySQL integration test.",
)
async def test_remote_mysql_async_connection_can_execute_sql():
    # 集成测试只在显式配置连接串时运行，避免普通单测依赖远程中间件。
    session_maker = create_session_maker(MYSQL_TEST_DATABASE_URL)

    async with session_maker() as session:
        result = await session.execute(text("SELECT 1"))

    assert result.scalar_one() == 1
