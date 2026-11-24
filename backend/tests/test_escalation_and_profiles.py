from __future__ import annotations

import json
from datetime import date
import pytest
from httpx import ASGITransport, AsyncClient

from tests.mocks import MockProvider
from app.gateway.router import VeritasRouter
from app.main import app
from app.models.schemas import (
    ClaimAuditResult,
    ExtractionBundle,
    ExtractedClaim,
    Lab,
    PolicyMode,
    Verdict,
)
from app.pipeline.s4_decide import evaluate_policy_verdict
from app.pipeline.veritas_engine import SourceDoc, VeritasPipeline


@pytest.mark.asyncio
async def test_critical_claim_in_strict_mode_escalates_to_human() -> None:
    bundle = ExtractionBundle(
        draft_answer="Category I AIF funds must maintain a 10 percent liquid cushion.",
        claims=[
            ExtractedClaim(
                claim_id="CLM-01",
                claim_text="Category I AIF funds must maintain a 10 percent liquid cushion.",
                is_factual=True,
                is_critical=True,
                verbatim_quote="Category I and II Alternative Investment Funds (AIFs) must maintain minimum 10 percent unencumbered liquid cushion",
                cited_doc_id="DOC-SEBI-01",
            )
        ],
    )
    audits = [
        ClaimAuditResult(
            claim_id="CLM-01",
            claim_text="Category I AIF funds must maintain a 10 percent liquid cushion.",
            is_factual=True,
            is_critical=True,
            quote_verified=True,
            numeric_mismatch=False,
            fy_mismatch=False,
            cross_lab_supported=True,
            matched_doc_id="DOC-SEBI-01",
            verbatim_quote="Category I and II Alternative Investment Funds (AIFs) must maintain minimum 10 percent unencumbered liquid cushion",
        )
    ]

    # In STRICT mode, critical regulatory claim routes to ESCALATE
    verdict, answer, warnings = evaluate_policy_verdict(
        bundle=bundle,
        audits=audits,
        policy=PolicyMode.STRICT,
        has_valid_sources=True,
    )
    assert verdict == Verdict.ESCALATE
    assert "ESCALATED FOR HUMAN REVIEW" in answer
    assert any("Critical regulatory claim" in w for w in warnings)

    # In BALANCED mode, same critical claim is auto-approved if quotes match
    verdict_b, _, _ = evaluate_policy_verdict(
        bundle=bundle,
        audits=audits,
        policy=PolicyMode.BALANCED,
        has_valid_sources=True,
    )
    assert verdict_b == Verdict.APPROVE


@pytest.mark.asyncio
async def test_scoped_app_key_enforces_policy_restriction() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a scoped API key restricted ONLY to 'strict' policy
        res = await client.post(
            "/v1/app-keys",
            json={
                "app_name": "Strict-Only-Client",
                "rate_limit_per_minute": 100,
                "allowed_policies": ["strict"],
            },
            headers={"X-Veritas-Key": "veritas-local-dev-key-2026"},
        )
        assert res.status_code == 201
        data = res.json()
        scoped_key = data["raw_key"]
        assert data["allowed_policies"] == ["strict"]

        # 2. Querying with permitted 'strict' policy succeeds
        res_ok = await client.post(
            "/v1/verify",
            json={
                "query": "What is the policy repo rate?",
                "policy": "strict",
                "reference_date": "2025-01-15",
            },
            headers={"X-Veritas-Key": scoped_key},
        )
        assert res_ok.status_code == 200

        # 3. Querying with unpermitted 'standard' policy is rejected with 403 Forbidden
        res_blocked = await client.post(
            "/v1/verify",
            json={
                "query": "What is the policy repo rate?",
                "policy": "standard",
                "reference_date": "2025-01-15",
            },
            headers={"X-Veritas-Key": scoped_key},
        )
        assert res_blocked.status_code == 403
        assert "restricted to policy profiles" in res_blocked.json()["detail"]


@pytest.mark.asyncio
async def test_human_review_signoff_endpoint() -> None:
    from app.api.routes import get_veritas_router
    test_router = VeritasRouter({
        Lab.ANTHROPIC: MockProvider(Lab.ANTHROPIC, "claude-3-5-sonnet"),
        Lab.OPENAI: MockProvider(Lab.OPENAI, "gpt-4o-mini"),
    })
    app.dependency_overrides[get_veritas_router] = lambda: test_router
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"X-Veritas-Key": "veritas-local-dev-key-2026"}

            # Seed approved source first so retrieval succeeds deterministically
            await client.post(
                "/v1/sources",
                json={
                    "doc_id": "DOC-SEBI-01",
                    "title": "SEBI Liquid Cushion Regulations",
                    "text": "Category I and II Alternative Investment Funds (AIFs) must maintain minimum 10 percent unencumbered liquid cushion for emergency exits.",
                    "valid_from": "2024-01-01",
                    "authority_tier": "regulatory",
                },
                headers=headers,
            )

            # 1. Trigger an escalation query (contains 'statutory' or 'critical' in query)
            verify_res = await client.post(
                "/v1/verify",
                json={
                    "query": "What is the statutory liquid cushion requirement for Category I Alternative Investment Funds?",
                    "policy": "strict",
                    "reference_date": "2025-01-15",
                },
                headers=headers,
            )
            assert verify_res.status_code == 200
            v_data = verify_res.json()
            audit_id = v_data["audit_id"]
            assert v_data["verdict"] == "ESCALATE"

            # 2. Compliance Officer signs off on the escalated audit
            review_res = await client.post(
                f"/v1/audits/{audit_id}/review",
                json={
                    "decision": "APPROVE",
                    "reviewer": "Officer Ananya Sen (Lead Compliance)",
                    "notes": "Verified against SEBI Circular Ref CIR/IMD/DF/2024.",
                },
                headers=headers,
            )
            assert review_res.status_code == 200
            r_data = review_res.json()
            assert r_data["previous_verdict"] == "ESCALATE"
            assert r_data["new_verdict"] == "APPROVE"
            assert r_data["is_safe_to_publish"] is True
    finally:
        app.dependency_overrides.pop(get_veritas_router, None)
