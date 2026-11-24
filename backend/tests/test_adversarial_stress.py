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


@pytest.mark.asyncio
async def test_concurrent_cross_lab_audit_fanout_selects_first_healthy_auditor() -> None:
    """Tests that concurrent audit fanout queries candidate secondary labs simultaneously and returns healthy result."""
    from app.gateway.base import LLMProvider

    class FailingSecondaryProvider(LLMProvider):
        lab = Lab.OPENAI
        model = "gpt-4o-mini"
        async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
            raise RuntimeError("429 Insufficient quota: credit_balance_exhausted")

    class WorkingSecondaryProvider(LLMProvider):
        lab = Lab.OLLAMA
        model = "llama3.2:latest"
        async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
            import json
            return json.dumps({"supported": True, "reason": "Entailed by source quote."})

    router = VeritasRouter({
        Lab.GOOGLE: MockProvider(Lab.GOOGLE, "gemini-3-flash-preview"),
        Lab.OPENAI: FailingSecondaryProvider(),
        Lab.OLLAMA: WorkingSecondaryProvider(),
    })

    # Generator is Google -> candidates are OpenAI and Ollama
    auditor_chain = router.get_auditor_chain(Lab.GOOGLE)
    assert Lab.GOOGLE not in auditor_chain
    assert Lab.OPENAI in auditor_chain
    assert Lab.OLLAMA in auditor_chain

    content, provider, telemetry = await router.call_cross_lab_concurrent(
        candidate_labs=auditor_chain,
        system_prompt="You are a compliance auditor",
        user_prompt="Verify claim",
        excluded_labs={Lab.GOOGLE},
    )

    assert provider.lab == Lab.OLLAMA
    assert "supported" in content


@pytest.mark.asyncio
async def test_ollama_provider_circuit_trips_on_connection_refusal_and_skips_in_0ms() -> None:
    """Verifies that an unreachable local LLM endpoint trips to OPEN immediately and subsequent calls skip in 0ms."""
    import time
    from app.gateway.adapters import OllamaProvider
    from app.gateway.circuit_breaker import CircuitBreakerManager, CircuitState
    from app.gateway.moe_router import MoERoute, MoERouter

    # Point to an unreachable port
    offline_provider = OllamaProvider(
        model="llama3.2:latest",
        base_url="http://127.0.0.1:59999/v1",
    )
    cb = CircuitBreakerManager(failure_threshold=1, cooldown_seconds=30.0, redis_url="inmemory")
    moe = MoERouter(providers={Lab.OLLAMA: offline_provider}, circuit_breaker=cb)

    # First attempt: connection refused -> trips circuit to OPEN
    with pytest.raises(Exception):
        await moe.execute_route(
            candidate_labs=[Lab.OLLAMA],
            system_prompt="system",
            user_prompt="hello",
            route=MoERoute.FAST_EXTRACTION,
        )

    # State must now be OPEN
    assert await cb.get_state(Lab.OLLAMA) == CircuitState.OPEN

    # Second attempt: must skip in 0ms without network call
    t0 = time.perf_counter()
    with pytest.raises(RuntimeError) as exc_info:
        await moe.execute_route(
            candidate_labs=[Lab.OLLAMA],
            system_prompt="system",
            user_prompt="hello",
            route=MoERoute.FAST_EXTRACTION,
        )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 50.0  # Skipped in 0ms
    assert "All circuits exhausted or excluded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_strict_abstention_when_all_secondary_auditors_fail() -> None:
    """Tests that in STRICT mode, if no secondary auditor can verify, engine strictly forces ABSTAIN with 'No answer possible'."""
    from app.pipeline.s3_examine_llm import audit_claim_with_cross_lab_model
    from app.pipeline.s4_decide import evaluate_policy_verdict
    from app.models.schemas import ExtractedClaim

    class ExhaustedProvider(MockProvider):
        async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
            raise RuntimeError("429 quota exhausted")

    router = VeritasRouter({
        Lab.GOOGLE: MockProvider(Lab.GOOGLE, "gemini-3-flash-preview"),
        Lab.OPENAI: ExhaustedProvider(Lab.OPENAI, "gpt-4o-mini"),
    })

    # 1. Cross-lab audit call fails
    supported, reason, auditor = await audit_claim_with_cross_lab_model(
        router=router,
        claim_text="Total outlay is ₹11,11,111 crore.",
        verbatim_quote="Total outlay is ₹11,11,111 crore.",
        generator_lab=Lab.GOOGLE,
    )
    assert supported is False
    assert auditor is None
    assert "unreachable or exhausted" in reason

    # 2. Policy evaluation in STRICT mode forces ABSTAIN
    from app.models.schemas import ClaimAuditResult, ExtractionBundle
    bundle = ExtractionBundle(
        draft_answer="Total outlay is ₹11,11,111 crore.",
        claims=[],
    )
    audit = ClaimAuditResult(
        claim_id="c1",
        claim_text="Total outlay is ₹11,11,111 crore.",
        is_factual=True,
        quote_verified=True,
        numeric_mismatch=False,
        fy_mismatch=False,
        cross_lab_supported=False,
        reasons=[reason],
        verbatim_quote="Total outlay is ₹11,11,111 crore.",
    )
    verdict, answer, _ = evaluate_policy_verdict(
        bundle=bundle,
        audits=[audit],
        policy=PolicyMode.STRICT,
        has_valid_sources=True,
    )
    assert verdict == Verdict.ABSTAIN
    assert answer == "No answer possible"


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
