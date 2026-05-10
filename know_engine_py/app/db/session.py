from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (AsyncSession,
                                     async_sessionmaker,
                                     create_async_engine,
                                    AsyncEngine
                                     )

from know_engine_py.app.core.settings import get_settings


def create_session_maker_from_engine(
        engine: AsyncEngine,
)->async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def create_session_maker(
    database_url: str,
    echo: bool = False,
) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
    )

    return create_session_maker_from_engine(engine)


@lru_cache
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    settings = get_settings()

    return create_session_maker(
        database_url=settings.database_url,
        echo=settings.database_echo,
    )


def reset_session_maker_cache() -> None:
    get_session_maker.cache_clear()


async def get_db() -> AsyncGenerator[AsyncSession]:
    session_maker = get_session_maker()

    async with session_maker() as session:
        yield session
