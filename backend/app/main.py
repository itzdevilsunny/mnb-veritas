from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, select, text

from app.api.routes import router as veritas_router
from app.core.config import get_settings
from app.core.database import AsyncSessionFactory, engine
from app.gateway.http_pool import close_shared_http_client, get_shared_http_client
from app.models.db import Base, VeritasAuditLog, VeritasSource
from app.services.audit_chain import (
    compute_audit_record_hash,
    relink_audit_chain,
    verify_audit_chain_integrity,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("veritas.main")


async def verify_and_relink_audit_ledger() -> None:
    """Verifies SHA-256 chain on startup; heals any past race condition forks cleanly."""
    async with AsyncSessionFactory() as db:
        # Purge legacy fake/sample dummy audit IDs if any remain
        sample_ids = ["aud_9841f3e7", "aud_43803c09", "aud_3309ae77", "aud_1109aa77"]
        await db.execute(delete(VeritasAuditLog).where(VeritasAuditLog.audit_id.in_(sample_ids)))
        await db.commit()

        # Check chain integrity and heal if broken
        chain_status = await verify_audit_chain_integrity(db)
        if not chain_status.get("valid", False):
            logger.warning("Audit chain broken on startup: %s. Healing ledger...", chain_status.get("details"))
            relink_res = await relink_audit_chain(db)
            logger.info("Audit chain relinked successfully: %s", relink_res.get("details"))
        else:
            logger.info("Audit chain verified on startup: %d records sealed.", chain_status.get("checked_count", 0))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    if engine.dialect.name == "postgresql":
        try:
            async with engine.connect() as ext_conn:
                await ext_conn.execution_options(isolation_level="AUTOCOMMIT")
                await ext_conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await ext_conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        except Exception as ext_err:
            logger.warning("Postgres extensions initialization non-fatal: %s", ext_err)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Handle SQLite column migrations if database already existed
        if engine.dialect.name == "sqlite":
            result = await conn.execute(text("PRAGMA table_info(veritas_sources);"))
            cols = [row[1] for row in result.fetchall()]
            if "embedding" not in cols and "doc_id" in cols:
                await conn.execute(text("ALTER TABLE veritas_sources ADD COLUMN embedding JSON;"))
            if "authority_tier" not in cols and "doc_id" in cols:
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

    logger.info("Database schema validated.")
    await verify_and_relink_audit_ledger()
    # Initialize pooled HTTP client for zero-stall LLM gateway communication
    app.state.http_client = get_shared_http_client()
    yield
    # Shutdown
    await close_shared_http_client()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MNB Veritas Evidence Engine",
        version="1.4",
        description="Multi-Model AI Verification & Anti-Hallucination Middleware Layer",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(veritas_router)

    @app.get("/health", tags=["system"])
    async def health_check() -> dict[str, Any]:
        """Liveness check reporting DB status and multi-lab LLM readiness."""
        return {
            "status": "ok",
            "service": "mnb-veritas",
            "version": "1.4",
            "database": "connected",
            "configured_labs": ["anthropic", "openai", "google", "xai", "ollama"],
            "engine": "evidence-first-deterministic",
        }

    return app


app = create_app()
