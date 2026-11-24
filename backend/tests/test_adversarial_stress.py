from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from tests.mocks import MockProvider
from app.gateway.router import VeritasRouter
from app.main import app
from app.models.schemas import Lab, PolicyMode, Verdict
from app.pipeline.s3_examine_code import (
    check_numeric_and_fy_consistency,
    extract_fy_tokens,
    extract_scaled_quantities,
    verify_verbatim_quote,
)
from app.pipeline.veritas_engine import SourceDoc, VeritasPipeline


# =====================================================================
# 1. SCALE MISMATCH & NUMERIC STRESS TESTS
# =====================================================================

def test_lakh_vs_crore_100x_scale_mismatch_detected() -> None:
    # ₹3 lakh (300,000) vs ₹3 crore (30,000,000) -> 100x error
    claim = "The sanctioned subsidy is ₹3 lakh per unit."
    quote = "The sanctioned subsidy is ₹3 crore per unit."
    num_bad, fy_bad, reasons = check_numeric_and_fy_consistency(claim, quote)
    assert num_bad is True
    assert fy_bad is False
    assert any("100x scale error" in r for r in reasons)


def test_claim_inventing_quantities_when_quote_has_none() -> None:
    claim = "The department allocated ₹500 crore for bridge reconstruction."
    quote = "The department approved bridge reconstruction works across coastal highways."
    num_bad, fy_bad, reasons = check_numeric_and_fy_consistency(claim, quote)
    assert num_bad is True
    assert any("contains no quantities" in r for r in reasons)


def test_claim_inventing_percentages_when_quote_has_none() -> None:
    claim = "The required minimum liquidity cushion is 15 percent."
    quote = "All funds must maintain an unencumbered liquid cushion for investor drawdowns."
    num_bad, fy_bad, reasons = check_numeric_and_fy_consistency(claim, quote)
    assert num_bad is True
    assert any("contains no percentages" in r for r in reasons)


# =====================================================================
# 2. FINANCIAL YEAR (FY) TOKEN STRESS TESTS
# =====================================================================

def test_claim_asserting_fy_when_quote_has_none() -> None:
    claim = "Capital expenditure outlay stands at ₹11,11,111 crore for FY 2025-26."
    quote = "Capital expenditure outlay stands at ₹11,11,111 crore."
    num_bad, fy_bad, reasons = check_numeric_and_fy_consistency(claim, quote)
    assert fy_bad is True
    assert num_bad is False
    assert any("contains no financial year reference" in r for r in reasons)


def test_fy_variations_reconciliation() -> None:
    # 'FY 2025-26', 'FY26', 'financial year 2025-26' all resolve to start year '2025'
    tokens1 = extract_fy_tokens("The outlay is approved for FY 2025-26.")
    tokens2 = extract_fy_tokens("The outlay is approved for FY26.")
    tokens3 = extract_fy_tokens("The outlay is approved for financial year 2025-26.")
    assert tokens1 == {"2025"}
    assert tokens2 == {"2025"}
    assert tokens3 == {"2025"}


# =====================================================================
# 3. MULTI-CHUNK PDF CITATIONS & PAGE BOUNDARIES
# =====================================================================

@pytest.mark.asyncio
async def test_multi_chunk_pdf_citation_and_metadata_preservation() -> None:
    sources = [
        SourceDoc(
            doc_id="ANNEX_CIRCULAR:p2:c3",
            title="Annexure Circular (p.2 / chunk 3)",
            text="The revised ceiling for micro-enterprises is ₹25 lakh effective April 2025.",
            valid_from=date(2025, 1, 1),
            valid_until=date(2026, 12, 31),
            metadata={"total_pages": 10, "page_number": 2, "chunk_index": 3},
        )
    ]
    router = VeritasRouter({
        Lab.ANTHROPIC: MockProvider(Lab.ANTHROPIC, "claude-3-5-sonnet"),
        Lab.OPENAI: MockProvider(Lab.OPENAI, "gpt-4o-mini"),
    })
    pipeline = VeritasPipeline(router=router, sources=sources)
    result = await pipeline.run(
        "What is the revised ceiling for micro-enterprises effective April 2025?",
        policy=PolicyMode.STRICT,
        ref_date=date(2025, 5, 1),
    )
    assert result.verdict == Verdict.APPROVE
    assert len(result.claim_audits) > 0
    claim_audit = result.claim_audits[0]
    assert claim_audit.matched_doc_id == "ANNEX_CIRCULAR:p2:c3"
    assert claim_audit.page_number == 2
    assert claim_audit.chunk_index == 3


# =====================================================================
# 4. TEMPORAL EXPIRY & STRICT ABSTENTION
# =====================================================================

@pytest.mark.asyncio
async def test_strict_abstention_on_expired_temporal_boundary() -> None:
    sources = [
        SourceDoc(
            doc_id="TEMP_POLICY_DOC",
            title="Expired Circular",
            text="Subsidy of 10% is applicable for solar pumps.",
            valid_from=date(2023, 1, 1),
            valid_until=date(2024, 12, 31),
        )
    ]
    router = VeritasRouter({
        Lab.ANTHROPIC: MockProvider(Lab.ANTHROPIC, "claude-3-5-sonnet"),
        Lab.OPENAI: MockProvider(Lab.OPENAI, "gpt-4o-mini"),
    })
    pipeline = VeritasPipeline(router=router, sources=sources)
    # Query evaluated in 2025 (past expiration)
    result = await pipeline.run(
        "What is the subsidy for solar pumps?",
        policy=PolicyMode.STRICT,
        ref_date=date(2025, 6, 1),
    )
    assert result.verdict == Verdict.ABSTAIN
    assert result.answer == "No answer possible"


# =====================================================================
# 5. CROSS-LAB AUDITOR INDEPENDENCE & FALLBACK HARDENING
# =====================================================================

@pytest.mark.asyncio
async def test_cross_lab_auditor_never_matches_primary_generator() -> None:
    # Router configured with mock providers
    providers = {
        Lab.ANTHROPIC: MockProvider(Lab.ANTHROPIC, "claude-3-5-sonnet"),
        Lab.OPENAI: MockProvider(Lab.OPENAI, "gpt-4o-mini"),
    }
    router = VeritasRouter(providers)

    # When generator is Anthropic, auditor chain must exclude Anthropic
    auditor_chain = router.get_auditor_chain(Lab.ANTHROPIC)
    assert Lab.ANTHROPIC not in auditor_chain
    assert Lab.OPENAI in auditor_chain

    # When calling with failover and excluding generator, returned provider cannot be Anthropic
    _, auditor_provider, _ = await router.call_with_failover(
        preferred_labs=auditor_chain,
        system_prompt="You are a compliance auditor",
        user_prompt="Audit this claim",
        excluded_labs={Lab.ANTHROPIC},
    )
    assert auditor_provider.lab != Lab.ANTHROPIC


# =====================================================================
# 6. CONCURRENT VERIFY & STREAMING LOAD TEST
# =====================================================================

@pytest.mark.asyncio
async def test_concurrent_verify_requests_without_starvation() -> None:
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

            async def send_verify(idx: int):
                return await client.post(
                    "/v1/verify",
                    json={
                        "query": "What is the policy repo rate?",
                        "policy": "strict",
                        "reference_date": "2025-01-15",
                    },
                    headers=headers,
                )

            # Run 8 concurrent verification requests
            responses = await asyncio.gather(*(send_verify(i) for i in range(8)))
            for resp in responses:
                assert resp.status_code == 200
                data = resp.json()
                assert "verdict" in data
                assert data["verdict"] in ["APPROVE", "QUALIFY", "ABSTAIN"]
    finally:
        app.dependency_overrides.pop(get_veritas_router, None)


# =====================================================================
# 7. CLEANUP ROUTE TEST
# =====================================================================

@pytest.mark.asyncio
async def test_cleanup_test_data_route() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-Veritas-Key": "veritas-local-dev-key-2026"}

        # 1. Register a temporary source
        await client.post(
            "/v1/sources",
            json={
                "doc_id": "TEMP_TEST_DOC_999",
                "title": "Temporary Test Source",
                "text": "Temporary content for cleanup verification.",
                "valid_from": "2025-01-01",
                "valid_until": "2025-12-31",
                "is_primary": False,
            },
            headers=headers,
        )

        # 2. Call cleanup endpoint
        cleanup_resp = await client.delete(
            "/v1/sources/cleanup-test-data?prefix=TEMP_",
            headers=headers,
        )
        assert cleanup_resp.status_code == 200
        res = cleanup_resp.json()
        assert res["status"] == "ok"
        assert res["deleted_sources_count"] >= 1
