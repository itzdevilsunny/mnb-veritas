from __future__ import annotations

import json
from datetime import date
import pytest

from veritas_engine import (
    Lab,
    MockProvider,
    PolicyMode,
    SourceDoc,
    Verdict,
    VeritasPipeline,
    VeritasRouter,
)


def _sample_sources() -> list[SourceDoc]:
    return [
        SourceDoc(
            doc_id="DOC-BUDGET-26",
            title="Annual Budget Circular FY 2025-26",
            text=(
                "Approved grant allocation for FY 2025-26 is Rs 2.5 crore across 12 districts. "
                "The maximum eligible grant per district is 25 percent of the total pool."
            ),
            valid_from=date(2025, 4, 1),
            valid_until=date(2027, 3, 31),
            is_primary=True,
        ),
        SourceDoc(
            doc_id="DOC-OLD-24",
            title="Legacy Circular FY 2023-24",
            text="Legacy grant allocation was Rs 1.0 crore.",
            valid_from=date(2023, 4, 1),
            valid_until=date(2024, 3, 31),
            is_primary=True,
        ),
    ]


@pytest.mark.asyncio
async def test_approves_when_quote_numbers_fy_and_cross_lab_audit_pass() -> None:
    generator = MockProvider(
        Lab.ANTHROPIC,
        "claude-sonnet-5-5",
        json.dumps(
            {
                "draft_answer": "Approved grant allocation for FY 2025-26 is Rs 2.5 crore across 12 districts.",
                "claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "Approved grant allocation for FY 2025-26 is Rs 2.5 crore.",
                        "is_factual": True,
                        "verbatim_quote": "Approved grant allocation for FY 2025-26 is Rs 2.5 crore",
                        "cited_doc_id": "DOC-BUDGET-26",
                    }
                ],
            }
        ),
    )
    auditor = MockProvider(
        Lab.GOOGLE,
        "gemini-4-hydrogen",
        json.dumps({"supported": True, "reason": "Faithful to verbatim quote."}),
    )

    pipeline = VeritasPipeline(
        router=VeritasRouter({Lab.ANTHROPIC: generator, Lab.GOOGLE: auditor}),
        sources=_sample_sources(),
    )
    report = await pipeline.run(
        "What is the approved grant allocation for FY 2025-26?",
        policy=PolicyMode.STRICT,
        ref_date=date(2026, 11, 22),
    )

    assert report.verdict == Verdict.APPROVE
    assert "2.5 crore" in report.answer
    assert report.model_used.startswith("anthropic:")
    assert report.auditor_model_used is not None
    assert report.auditor_model_used.startswith("google:")


@pytest.mark.asyncio
async def test_abstains_with_no_answer_possible_when_citation_missing() -> None:
    generator = MockProvider(
        Lab.ANTHROPIC,
        "claude-sonnet-5-5",
        json.dumps(
            {
                "draft_answer": "The reserve fund holds Rs 80 crore in sovereign bonds.",
                "claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "The reserve fund holds Rs 80 crore in sovereign bonds.",
                        "is_factual": True,
                        "verbatim_quote": None,
                        "cited_doc_id": None,
                    }
                ],
            }
        ),
    )
    auditor = MockProvider(Lab.OPENAI, "gpt-4o", json.dumps({"supported": False, "reason": "No source"}))

    pipeline = VeritasPipeline(
        router=VeritasRouter({Lab.ANTHROPIC: generator, Lab.OPENAI: auditor}),
        sources=_sample_sources(),
    )
    report = await pipeline.run(
        "How much is held in sovereign bonds?",
        policy=PolicyMode.STRICT,
        ref_date=date(2026, 11, 22),
    )

    assert report.verdict == Verdict.ABSTAIN
    assert report.answer == "No answer possible"


@pytest.mark.asyncio
async def test_abstains_with_no_answer_possible_on_numeric_or_fy_mismatch() -> None:
    generator = MockProvider(
        Lab.ANTHROPIC,
        "claude-sonnet-5-5",
        json.dumps(
            {
                "draft_answer": "Approved grant allocation for FY 2026-27 is Rs 25 crore.",
                "claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "Approved grant allocation for FY 2026-27 is Rs 25 crore.",
                        "is_factual": True,
                        "verbatim_quote": "Approved grant allocation for FY 2025-26 is Rs 2.5 crore across 12 districts.",
                        "cited_doc_id": "DOC-BUDGET-26",
                    }
                ],
            }
        ),
    )
    # Even if an external model claims supported, code must enforce rejection
    auditor = MockProvider(Lab.GOOGLE, "gemini-4-hydrogen", json.dumps({"supported": True, "reason": "ok"}))

    pipeline = VeritasPipeline(
        router=VeritasRouter({Lab.ANTHROPIC: generator, Lab.GOOGLE: auditor}),
        sources=_sample_sources(),
    )
    report = await pipeline.run(
        "What is the FY 2026-27 grant allocation?",
        policy=PolicyMode.STRICT,
        ref_date=date(2026, 11, 22),
    )

    assert report.verdict == Verdict.ABSTAIN
    assert report.answer == "No answer possible"
    assert report.claim_audits[0].numeric_mismatch is True
    assert report.claim_audits[0].fy_mismatch is True


@pytest.mark.asyncio
async def test_abstains_with_no_answer_possible_when_no_sources_exist() -> None:
    generator = MockProvider(
        Lab.ANTHROPIC,
        "claude-sonnet-5-5",
        json.dumps({"draft_answer": "Some answer", "claims": []}),
    )
    pipeline = VeritasPipeline(
        router=VeritasRouter({Lab.ANTHROPIC: generator}),
        sources=[],
    )
    report = await pipeline.run("Any ungrounded question?", policy=PolicyMode.STRICT)

    assert report.verdict == Verdict.ABSTAIN
    assert report.answer == "No answer possible"
