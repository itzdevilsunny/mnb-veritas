from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from app.core.config import get_settings

_settings = get_settings()

# Engine creation supporting SQLite async and PostgreSQL asyncpg
db_url = _settings.DATABASE_URL
engine_kwargs = {"echo": False, "future": True}

if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
elif "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
    engine_kwargs["poolclass"] = NullPool

engine: AsyncEngine = create_async_engine(db_url, **engine_kwargs)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        finally:
            await session.close()
