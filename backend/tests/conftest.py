from __future__ import annotations

import pytest
from sqlalchemy import text
from app.core.database import engine
from app.gateway.circuit_breaker import get_circuit_breaker
from app.models.db import Base
from app.models.schemas import Lab


@pytest.fixture(autouse=True)
async def reset_circuit_breakers_and_sync_db():
    """Ensures DB schema is up to date and circuit breakers are clean before and after each test."""
    async with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        await conn.run_sync(Base.metadata.create_all)

        if engine.dialect.name == "sqlite":
            res_src = await conn.execute(text("PRAGMA table_info(veritas_sources);"))
            cols_src = [row[1] for row in res_src.fetchall()]
            if "embedding" not in cols_src and "doc_id" in cols_src:
                await conn.execute(text("ALTER TABLE veritas_sources ADD COLUMN embedding JSON;"))

            res_keys = await conn.execute(text("PRAGMA table_info(veritas_app_keys);"))
            cols_keys = [row[1] for row in res_keys.fetchall()]
            if "allowed_policies" not in cols_keys and "id" in cols_keys:
                await conn.execute(text("ALTER TABLE veritas_app_keys ADD COLUMN allowed_policies JSON DEFAULT '[\"standard\",\"balanced\",\"strict\"]';"))

    cb = get_circuit_breaker()
    for lab in [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI]:
        await cb.reset(lab)
    yield
    for lab in [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI]:
        await cb.reset(lab)

