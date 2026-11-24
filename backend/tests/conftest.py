from __future__ import annotations

import pytest
from sqlalchemy import text
from app.core.database import engine
from app.gateway.circuit_breaker import get_circuit_breaker
from app.models.db import Base
from app.models.schemas import Lab

_db_initialized = False


@pytest.fixture(autouse=True)
async def reset_circuit_breakers_and_sync_db():
    """
    Ensures DB schema is initialized once per test session and circuit breakers
    are cleanly reset before and after each test function.
    Prevents asyncpg connection locking collisions across async tests.
    """
    global _db_initialized
    if not _db_initialized:
        _db_initialized = True
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

                if engine.dialect.name == "sqlite":
                    res_src = await conn.execute(text("PRAGMA table_info(veritas_sources);"))
                    cols_src = [row[1] for row in res_src.fetchall()]
                    if "embedding" not in cols_src and "doc_id" in cols_src:
                        await conn.execute(text("ALTER TABLE veritas_sources ADD COLUMN embedding JSON;"))
                    if "authority_tier" not in cols_src and "doc_id" in cols_src:
                        await conn.execute(text("ALTER TABLE veritas_sources ADD COLUMN authority_tier VARCHAR(32) DEFAULT 'regulatory';"))

                    res_keys = await conn.execute(text("PRAGMA table_info(veritas_app_keys);"))
                    cols_keys = [row[1] for row in res_keys.fetchall()]
                    if "allowed_policies" not in cols_keys and "id" in cols_keys:
                        await conn.execute(text("ALTER TABLE veritas_app_keys ADD COLUMN allowed_policies JSON DEFAULT '[\"standard\",\"balanced\",\"strict\"]';"))

                    res_audits = await conn.execute(text("PRAGMA table_info(veritas_audit_logs);"))
                    cols_audits = [row[1] for row in res_audits.fetchall()]
                    if "prev_hash" not in cols_audits and "audit_id" in cols_audits:
                        await conn.execute(text("ALTER TABLE veritas_audit_logs ADD COLUMN prev_hash VARCHAR(64);"))
                    if "record_hash" not in cols_audits and "audit_id" in cols_audits:
                        await conn.execute(text("ALTER TABLE veritas_audit_logs ADD COLUMN record_hash VARCHAR(64);"))
        except Exception:
            pass

    cb = get_circuit_breaker()
    for lab in [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI, Lab.OLLAMA]:
        await cb.reset(lab)
    yield
    for lab in [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI, Lab.OLLAMA]:
        await cb.reset(lab)
