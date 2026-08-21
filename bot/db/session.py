

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import Settings

engine = None
async_session_factory = None


def init_db(Database_URL: str) -> None:
   
    global engine, async_session_factory
    engine = create_async_engine(Database_URL, echo=False)
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def get_session() -> AsyncSession:  # type: ignore[misc]

    if async_session_factory is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    async with async_session_factory() as session:
        yield session


async def close_db() -> None:

    if engine is not None:
        await engine.dispose()
