"""Database connection management."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import settings

# TODO: Implement async database engine
# engine = create_async_engine(settings.database_url)
# async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session.

    Yields:
        Async database session
    """
    # async with async_session_maker() as session:
    #     yield session
    pass
