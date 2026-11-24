from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import date, datetime, timezone
from typing import Any
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import get_db_session, get_veritas_router, router as veritas_router
from app.core.config import get_settings
from app.models.db import Base, VeritasAuditLog, VeritasSource
from app.models.schemas import ComplianceCertificateResponse
from app.services.audit_chain import compute_audit_record_hash
from app.services.certificate import (
    build_certificate_data,
    compute_certificate_seal,
    render_certificate_pdf,
)
from tests.mocks import MockProvider
from veritas_engine import Lab, VeritasRouter


@pytest_asyncio.fixture
async def certificate_app() -> AsyncGenerator[tuple[FastAPI, async_sessionmaker[AsyncSession]], None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI(title="MNB Veritas Option D Certificate Test App")
    app.include_router(veritas_router)

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    generator = MockProvider(
        Lab.ANTHROPIC,
        "claude-sonnet-5-5",
        json.dumps(
            {
                "draft_answer": "Budget allocation for Green Hydrogen is Rs 19,744 crore.",
                "claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "Budget allocation for Green Hydrogen is Rs 19,744 crore.",
                        "is_factual": True,
                        "verbatim_quote": "The Strategic Interventions for Green Hydrogen Transition has an outlay of Rs 19,744 crore.",
                        "cited_doc_id": "doc_hydrogen_2025",
                    }
                ],
            }
        ),
    )
    auditor = MockProvider(
        Lab.GOOGLE,
        "gemini-flash-latest",
        json.dumps({"supported": True, "reason": "Verbatim quote verified against policy doc."}),
    )
    mock_router = VeritasRouter({Lab.ANTHROPIC: generator, Lab.GOOGLE: auditor})

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_veritas_router] = lambda: mock_router

    # Seed source and verified audit record
    async with session_factory() as db:
        src = VeritasSource(
            doc_id="doc_hydrogen_2025",
            title="National Green Hydrogen Mission Document",
            text="The Strategic Interventions for Green Hydrogen Transition has an outlay of Rs 19,744 crore.",
            valid_from=date(2025, 1, 1),
            valid_until=None,
            authority_tier="statutory",
        )
        db.add(src)

        # First audit log
        created_time = datetime.now(timezone.utc)
        claim_audits_data = [
            {
                "claim_id": "c1",
                "claim_text": "Budget allocation for Green Hydrogen is Rs 19,744 crore.",
                "verbatim_quote": "The Strategic Interventions for Green Hydrogen Transition has an outlay of Rs 19,744 crore.",
                "matched_doc_id": "doc_hydrogen_2025",
                "quote_verified": True,
                "numeric_mismatch": False,
                "fy_mismatch": False,
                "cross_lab_supported": True,
            }
        ]
        rec_hash = compute_audit_record_hash(
            prev_hash="GENESIS",
            audit_id="aud_test_cert_01",
            created_at=created_time,
            verdict="APPROVE",
            policy_applied="strict",
            primary_model="anthropic:claude-sonnet-5-5",
            auditor_model="google:gemini-flash-latest",
            claim_audits=claim_audits_data,
        )

        audit = VeritasAuditLog(
            audit_id="aud_test_cert_01",
            query_text="What is the budget for Green Hydrogen?",
            answer="Budget allocation for Green Hydrogen is Rs 19,744 crore.",
            verdict="APPROVE",
            policy_applied="strict",
            primary_model="anthropic:claude-sonnet-5-5",
            auditor_model="google:gemini-flash-latest",
            failover_triggered=False,
            latency_ms=120,
            estimated_cost_usd=0.0015,
            claim_audits=claim_audits_data,
            warnings=[],
            prev_hash="GENESIS",
            record_hash=rec_hash,
            created_at=created_time,
        )
        db.add(audit)
        await db.commit()

    yield app, session_factory


@pytest.mark.asyncio
async def test_certificate_service_unit_methods():
    claim_audits_data = [
        {
            "claim_id": "c1",
            "claim_text": "Allocation is Rs 19,744 crore.",
            "verbatim_quote": "Total outlay is Rs 19,744 crore.",
            "matched_doc_id": "doc_ghm",
            "quote_verified": True,
        }
    ]
    audit = VeritasAuditLog(
        audit_id="aud_unit_test_99",
        query_text="What is the allocation?",
        answer="Allocation is Rs 19,744 crore.",
        created_at=datetime(2025, 4, 1, 10, 0, 0, tzinfo=timezone.utc),
        verdict="APPROVE",
        policy_applied="strict",
        primary_model="anthropic:claude-3-7-sonnet",
        auditor_model="google:gemini-2.5-pro",
        failover_triggered=False,
        latency_ms=115,
        estimated_cost_usd=0.002,
        claim_audits=claim_audits_data,
        warnings=[],
        prev_hash="GENESIS",
        record_hash="a" * 64,
    )

    cert_data = build_certificate_data(audit, chain_verified=True)
    assert cert_data.audit_id == "aud_unit_test_99"
    assert cert_data.chain_verified is True
    assert cert_data.verdict == "APPROVE"
    assert len(cert_data.verified_quotes) == 1

    seal = compute_certificate_seal(
        audit_id=audit.audit_id,
        record_hash=audit.record_hash,
        prev_hash=audit.prev_hash,
        verdict=audit.verdict,
        policy_applied=audit.policy_applied,
        primary_model=audit.primary_model,
        auditor_model=audit.auditor_model,
        chain_verified=True,
    )
    assert isinstance(seal, str)
    assert len(seal) == 64

    # Test PDF rendering
    pdf_bytes = render_certificate_pdf(cert_data)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


@pytest.mark.asyncio
async def test_certificate_endpoint_json_format(
    certificate_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
):
    app, _ = certificate_app
    settings = get_settings()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.get(
            "/v1/audits/aud_test_cert_01/certificate?format=json",
            headers={"X-Veritas-Key": settings.VERITAS_API_KEY},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["audit_id"] == "aud_test_cert_01"
        assert data["verdict"] == "APPROVE"
        assert data["safe_to_publish"] is True
        assert data["policy_applied"] == "strict"
        assert data["chain_verified"] is True
        assert len(data["certificate_seal_sha256"]) == 64
        assert len(data["verified_quotes"]) == 1
        assert data["verified_quotes"][0]["matched_doc_id"] == "doc_hydrogen_2025"

        # Validate with pydantic
        parsed = ComplianceCertificateResponse.model_validate(data)
        assert parsed.audit_id == "aud_test_cert_01"


@pytest.mark.asyncio
async def test_certificate_endpoint_pdf_format(
    certificate_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
):
    app, _ = certificate_app
    settings = get_settings()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.get(
            "/v1/audits/aud_test_cert_01/certificate?format=pdf",
            headers={"X-Veritas-Key": settings.VERITAS_API_KEY},
        )
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert "veritas-certificate-aud_test_cert_01.pdf" in res.headers["content-disposition"]
        assert res.content.startswith(b"%PDF-")
        assert len(res.content) > 1000


@pytest.mark.asyncio
async def test_certificate_endpoint_not_found(
    certificate_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
):
    app, _ = certificate_app
    settings = get_settings()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.get(
            "/v1/audits/aud_does_not_exist/certificate",
            headers={"X-Veritas-Key": settings.VERITAS_API_KEY},
        )
        assert res.status_code == 404
        assert "aud_does_not_exist" in res.json()["detail"]


@pytest.mark.asyncio
async def test_certificate_endpoint_unauthorized(
    certificate_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
):
    app, _ = certificate_app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.get("/v1/audits/aud_test_cert_01/certificate")
        assert res.status_code == 401
