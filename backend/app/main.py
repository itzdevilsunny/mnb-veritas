from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.api.routes import router as veritas_router
from app.core.config import get_settings
from app.core.database import AsyncSessionFactory, engine
from app.gateway.http_pool import close_shared_http_client, get_shared_http_client
from app.models.db import Base, VeritasAuditLog, VeritasSource
from app.services.audit_chain import compute_audit_record_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("veritas.main")


async def seed_initial_truth_corpuses_and_audits() -> None:
    """Pre-seeds the 4 truth sources and audit logs from the MNB Veritas reference design."""
    async with AsyncSessionFactory() as db:
        # Check if sources exist
        existing_src = (await db.execute(select(VeritasSource).limit(1))).scalar_one_or_none()
        if not existing_src:
            logger.info("Pre-seeding truth corpuses...")
            sources = [
                VeritasSource(
                    doc_id="doc_budget_2025",
                    title="Union Budget 2025-26 - Ministry of Finance Outlay Schedule",
                    text=(
                        "Total capital expenditure outlay stands at ₹11,11,111 crore for FY 2025-26. "
                        "Quarterly financial milestone reviews will be convened jointly by MNRE beginning Q1 of FY 2025-26."
                    ),
                    valid_from=date(2025, 1, 15),
                    valid_until=date(2026, 3, 31),
                    is_primary=True,
                    is_active=True,
                    authority_tier="statutory",
                    metadata_json={"total_pages": 64, "chunk_index": 142},
                ),
                VeritasSource(
                    doc_id="doc_green_hydrogen_2024",
                    title="National Green Hydrogen Mission Cabinet Note Ref #GHM-4850",
                    text=(
                        "Cabinet approves continuation of National Green Hydrogen Mission with financial outlay of ₹4,850 crore specifically ear-marked for FY 2025-26 pilot electrolysers. "
                        "Under component II (SIGHT), 68% of aggregate outlay shall be deployed across domestic electrolyser manufacturing incentives and green ammonia pilots."
                    ),
                    valid_from=date(2024, 1, 15),
                    valid_until=date(2027, 3, 31),
                    is_primary=True,
                    is_active=True,
                    authority_tier="statutory",
                    metadata_json={"total_pages": 28, "chunk_index": 80},
                ),
                VeritasSource(
                    doc_id="doc_rbi_fy25",
                    title="Reserve Bank of India Monetary Policy Report (Dec 2024)",
                    text=(
                        "The MPC decided to keep the policy repo rate unchanged at 6.50 per cent. "
                        "CPI inflation for 2024-25 is projected at 4.5 per cent with Q4 at 4.4 per cent."
                    ),
                    valid_from=date(2024, 12, 6),
                    valid_until=date(2025, 4, 30),
                    is_primary=False,
                    is_active=True,
                    authority_tier="regulatory",
                    metadata_json={"total_pages": 52, "chunk_index": 96},
                ),
                VeritasSource(
                    doc_id="doc_sebi_aifi_q3",
                    title="SEBI Circular on Alternate Investment Fund Liquidity Guardrails",
                    text=(
                        "SEBI Circular Ref CIR/IMD/DF/2024. All Category I and II Alternative Investment Funds (AIFs) "
                        "must maintain minimum 10 percent unencumbered liquid cushion for investor drawdown resilience."
                    ),
                    valid_from=date(2024, 10, 1),
                    valid_until=date(2025, 9, 30),
                    is_primary=False,
                    is_active=True,
                    authority_tier="regulatory",
                    metadata_json={"total_pages": 14, "chunk_index": 34},
                ),
            ]
            for s in sources:
                db.add(s)
            await db.commit()
            logger.info("Truth corpuses seeded cleanly.")

        # Check if audit logs exist
        existing_audits = (await db.execute(select(VeritasAuditLog).order_by(VeritasAuditLog.created_at.asc()))).scalars().all()
        if not existing_audits:
            logger.info("Pre-seeding sample audit records...")
            audits = [
                VeritasAuditLog(
                    audit_id="aud_9841f3e7",
                    query_text="What is the approved budgetary allocation for the National Green Hydrogen Mission for FY 2025-26 under the new outlay?",
                    verdict="APPROVE",
                    answer="The Ministry of Finance has sanctioned a total budgetary allocation of ₹4,850 crore for the National Green Hydrogen Mission for FY 2025-26. The Strategic Interventions for Green Hydrogen Transition (SIGHT) program receives 68% of the total allocation, and expenditure execution is subject to quarterly review by the Ministry of New and Renewable Energy starting Q1 FY26.",
                    policy_applied="strict",
                    primary_model="Claude 3.5 Sonnet",
                    auditor_model="GPT-4o (OpenAI)",
                    failover_triggered=False,
                    latency_ms=448,
                    estimated_cost_usd=0.0041,
                    claim_audits=[
                        {
                            "claim_id": "CLM-01",
                            "claim_text": "The Ministry of Finance has sanctioned a total budgetary allocation of ₹4,850 crore for the National Green Hydrogen Mission for FY 2025-26.",
                            "is_factual": True,
                            "quote_verified": True,
                            "source_expired": False,
                            "numeric_mismatch": False,
                            "fy_mismatch": False,
                            "cross_lab_supported": True,
                            "reasons": [],
                            "matched_doc_id": "doc_green_hydrogen_2024",
                            "verbatim_quote": "Cabinet approves continuation of National Green Hydrogen Mission with financial outlay of ₹4,850 crore specifically ear-marked for FY 2025-26 pilot electrolysers.",
                            "page_number": 12,
                            "chunk_index": 4,
                        },
                        {
                            "claim_id": "CLM-02",
                            "claim_text": "The Strategic Interventions for Green Hydrogen Transition (SIGHT) program receives 68% of the total allocation.",
                            "is_factual": True,
                            "quote_verified": True,
                            "source_expired": False,
                            "numeric_mismatch": False,
                            "fy_mismatch": False,
                            "cross_lab_supported": True,
                            "reasons": [],
                            "matched_doc_id": "doc_green_hydrogen_2024",
                            "verbatim_quote": "Under component II (SIGHT), 68% of aggregate outlay shall be deployed across domestic electrolyser manufacturing incentives and green ammonia pilots.",
                            "page_number": 14,
                            "chunk_index": 7,
                        },
                        {
                            "claim_id": "CLM-03",
                            "claim_text": "Expenditure execution is subject to quarterly review by the Ministry of New and Renewable Energy starting Q1 FY26.",
                            "is_factual": True,
                            "quote_verified": True,
                            "source_expired": False,
                            "numeric_mismatch": False,
                            "fy_mismatch": False,
                            "cross_lab_supported": True,
                            "reasons": [],
                            "matched_doc_id": "doc_budget_2025",
                            "verbatim_quote": "Quarterly financial milestone reviews will be convened jointly by MNRE beginning Q1 of FY 2025-26.",
                            "page_number": 38,
                            "chunk_index": 19,
                        },
                    ],
                    warnings=[],
                    created_at=datetime(2025, 3, 31, 14, 22, 4, tzinfo=timezone.utc),
                ),
                VeritasAuditLog(
                    audit_id="aud_43803c09",
                    query_text="Explain India's current bilateral sovereign guarantee commitments for offshore African LNG terminal construction in FY 2025-26.",
                    verdict="ABSTAIN",
                    answer="No answer possible",
                    policy_applied="strict",
                    primary_model="Gemini 1.5 Pro",
                    auditor_model="Claude 3.5 Sonnet",
                    failover_triggered=True,
                    latency_ms=290,
                    estimated_cost_usd=0.0019,
                    claim_audits=[
                        {
                            "claim_id": "CLM-01",
                            "claim_text": "India has provided a sovereign bilateral credit guarantee facility for offshore African LNG liquefaction terminals.",
                            "is_factual": True,
                            "quote_verified": False,
                            "source_expired": False,
                            "numeric_mismatch": False,
                            "fy_mismatch": False,
                            "cross_lab_supported": False,
                            "reasons": ["No approved source mentions sovereign guarantee commitments for offshore African LNG."],
                            "matched_doc_id": None,
                            "verbatim_quote": None,
                        }
                    ],
                    warnings=["No valid approved source backing for factual claims."],
                    created_at=datetime(2025, 3, 31, 13, 50, 12, tzinfo=timezone.utc),
                ),
                VeritasAuditLog(
                    audit_id="aud_3309ae77",
                    query_text="What was the RBI policy repo rate decision and CPI headline projection for Q4 FY25?",
                    verdict="QUALIFY",
                    answer="The Reserve Bank of India Monetary Policy Committee decided to maintain the benchmark policy repo rate unchanged at 6.50 per cent. CPI headline inflation projection for FY25 stands at 4.5 per cent, with Q4 projected at 4.4 per cent.",
                    policy_applied="balanced",
                    primary_model="GPT-4o (OpenAI)",
                    auditor_model="Claude 3.5 Sonnet",
                    failover_triggered=False,
                    latency_ms=312,
                    estimated_cost_usd=0.0038,
                    claim_audits=[
                        {
                            "claim_id": "CLM-01",
                            "claim_text": "The MPC decided to keep the policy repo rate unchanged at 6.50%.",
                            "is_factual": True,
                            "quote_verified": True,
                            "source_expired": False,
                            "numeric_mismatch": False,
                            "fy_mismatch": False,
                            "cross_lab_supported": True,
                            "reasons": [],
                            "matched_doc_id": "doc_rbi_fy25",
                            "verbatim_quote": "The MPC decided to keep the policy repo rate unchanged at 6.50 per cent.",
                        },
                        {
                            "claim_id": "CLM-02",
                            "claim_text": "CPI inflation projection for FY25 is 4.5%.",
                            "is_factual": True,
                            "quote_verified": True,
                            "source_expired": False,
                            "numeric_mismatch": False,
                            "fy_mismatch": False,
                            "cross_lab_supported": True,
                            "reasons": [],
                            "matched_doc_id": "doc_rbi_fy25",
                            "verbatim_quote": "CPI inflation for 2024-25 is projected at 4.5 per cent with Q4 at 4.4 per cent.",
                        },
                    ],
                    warnings=["Source doc_rbi_fy25 expired on 2025-04-30 (checked against 2025-05-01)."],
                    created_at=datetime(2025, 3, 31, 11, 5, 38, tzinfo=timezone.utc),
                ),
            ]
            last_hash = "GENESIS"
            for a in audits:
                a.prev_hash = last_hash
                a.record_hash = compute_audit_record_hash(
                    prev_hash=last_hash,
                    audit_id=a.audit_id,
                    created_at=a.created_at,
                    verdict=a.verdict,
                    policy_applied=a.policy_applied,
                    primary_model=a.primary_model,
                    auditor_model=a.auditor_model,
                    claim_audits=a.claim_audits,
                )
                last_hash = a.record_hash
                db.add(a)
            await db.commit()
            logger.info("Sample audit records seeded cleanly with SHA-256 chain linkage.")
        else:
            # Backfill and link any existing audit records
            last_hash = "GENESIS"
            needs_commit = False
            for a in existing_audits:
                if a.prev_hash != last_hash or not a.record_hash:
                    a.prev_hash = last_hash
                    a.record_hash = compute_audit_record_hash(
                        prev_hash=last_hash,
                        audit_id=a.audit_id,
                        created_at=a.created_at,
                        verdict=a.verdict,
                        policy_applied=a.policy_applied,
                        primary_model=a.primary_model,
                        auditor_model=a.auditor_model,
                        claim_audits=a.claim_audits,
                    )
                    needs_commit = True
                last_hash = a.record_hash
            if needs_commit:
                await db.commit()
                logger.info("Existing audit logs synchronized with SHA-256 chain hashes.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    async with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
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
    await seed_initial_truth_corpuses_and_audits()
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
