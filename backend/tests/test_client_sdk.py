from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add client directory to sys.path for test discovery
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "client"))

from app.api.routes import get_db_session, get_veritas_router, router as veritas_router
from app.core.config import get_settings
from app.models.db import Base, VeritasAuditLog, VeritasSource, utcnow
from app.services.audit_chain import compute_audit_record_hash
from tests.mocks import MockProvider
from veritas import VeritasClient, VeritasSyncClient, Verdict
from veritas.cli import create_parser
from veritas_engine import Lab, VeritasRouter


@pytest.fixture
def parser():
    return create_parser()


def test_cli_parser_commands(parser):
    # Verify subcommand
    args = parser.parse_args(["verify", "What is capex?", "--policy", "strict", "--export-cert", "test.pdf"])
    assert args.command == "verify"
    assert args.query == "What is capex?"
    assert args.policy == "strict"
    assert args.export_cert == "test.pdf"

    # Chain subcommand
    args_chain = parser.parse_args(["chain", "--json"])
    assert args_chain.command == "chain"
    assert args_chain.json is True

    # Health subcommand
    args_health = parser.parse_args(["health"])
    assert args_health.command == "health"

    # Cert subcommand
    args_cert = parser.parse_args(["cert", "aud_12345", "--format", "json", "--out", "seal.json"])
    assert args_cert.command == "cert"
    assert args_cert.audit_id == "aud_12345"
    assert args_cert.format == "json"
    assert args_cert.out == "seal.json"


@pytest.mark.asyncio
async def test_veritas_sdk_against_app():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI(title="SDK Test App")
    app.include_router(veritas_router)

    async def _override_db():
        async with session_factory() as session:
            yield session

    generator = MockProvider(
        Lab.ANTHROPIC,
        "claude-sonnet-5-5",
        json.dumps(
            {
                "draft_answer": "Budget allocation is Rs 10,000 crore.",
                "claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "Budget allocation is Rs 10,000 crore.",
                        "is_factual": True,
                        "verbatim_quote": "Approved allocation is Rs 10,000 crore.",
                        "cited_doc_id": "doc_sdk_01",
                    }
                ],
            }
        ),
    )
    auditor = MockProvider(
        Lab.GOOGLE,
        "gemini-flash-latest",
        json.dumps({"supported": True, "reason": "Verbatim quote matches."}),
    )
    mock_router = VeritasRouter({Lab.ANTHROPIC: generator, Lab.GOOGLE: auditor})

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_veritas_router] = lambda: mock_router

    # Seed an initial audit log and source
    async with session_factory() as db:
        src = VeritasSource(
            doc_id="doc_sdk_01",
            title="SDK Test Source",
            text="Approved allocation is Rs 10,000 crore.",
            valid_from=utcnow().date(),
            valid_until=None,
            authority_tier="statutory",
        )
        db.add(src)

        audit_time = utcnow()
        claim_audits_data = [
            {
                "claim_id": "c1",
                "claim_text": "Budget allocation is Rs 10,000 crore.",
                "verbatim_quote": "Approved allocation is Rs 10,000 crore.",
                "matched_doc_id": "doc_sdk_01",
                "quote_verified": True,
                "numeric_mismatch": False,
                "fy_mismatch": False,
                "cross_lab_supported": True,
            }
        ]
        rec_hash = compute_audit_record_hash(
            prev_hash="GENESIS",
            audit_id="aud_sdk_cert_01",
            created_at=audit_time,
            verdict="APPROVE",
            policy_applied="strict",
            primary_model="anthropic:claude-sonnet-5-5",
            auditor_model="google:gemini-flash-latest",
            claim_audits=claim_audits_data,
        )

        audit = VeritasAuditLog(
            audit_id="aud_sdk_cert_01",
            query_text="What is the budget?",
            answer="Budget allocation is Rs 10,000 crore.",
            verdict="APPROVE",
            policy_applied="strict",
            primary_model="anthropic:claude-sonnet-5-5",
            auditor_model="google:gemini-flash-latest",
            failover_triggered=False,
            latency_ms=105,
            estimated_cost_usd=0.0018,
            claim_audits=claim_audits_data,
            warnings=[],
            prev_hash="GENESIS",
            record_hash=rec_hash,
            created_at=audit_time,
        )
        db.add(audit)
        await db.commit()

    settings = get_settings()
    transport = httpx.ASGITransport(app=app)
    custom_http = httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-Veritas-Key": settings.VERITAS_API_KEY},
    )

    async with VeritasClient(api_url="http://testserver", api_key=settings.VERITAS_API_KEY, httpx_client=custom_http) as client:
        # 1. Test verify
        res = await client.verify(query="What is the budget?", policy="strict")
        assert res.audit_id.startswith("aud_")
        assert res.is_approved is True
        assert res.is_abstained is False
        assert res.claims_count == 1
        assert res.verified_quotes_count == 1

        # 2. Test verify_batch
        batch_res = await client.verify_batch([
            {"item_id": "b1", "query": "What is the budget?", "policy": "strict"},
            {"item_id": "b2", "query": "What is the budget?", "policy": "standard"},
        ])
        assert batch_res.total == 2
        assert batch_res.successful == 2
        assert len(batch_res.results) == 2

        # 3. Test download_certificate (PDF)
        pdf_bytes = await client.download_certificate("aud_sdk_cert_01", format="pdf")
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF-")

        # 4. Test download_certificate (JSON)
        seal_json = await client.download_certificate("aud_sdk_cert_01", format="json")
        assert isinstance(seal_json, dict)
        assert seal_json["audit_id"] == "aud_sdk_cert_01"
        assert len(seal_json["certificate_seal_sha256"]) == 64

        # 5. Test verify_chain
        chain = await client.verify_chain()
        assert chain.valid is True
        assert chain.checked_count >= 1
