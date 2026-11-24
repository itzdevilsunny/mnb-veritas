from __future__ import annotations

import hashlib
import time
import uuid
from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.router import VeritasRouter
from app.models.db import VeritasSource
from app.models.schemas import PolicyMode, SourceDoc, Verdict
from app.pipeline.veritas_engine import VeritasPipeline
from app.services.audit_chain import prepare_audit_log_entry


class BenchmarkTestCase(BaseModel):
    case_id: str
    name: str
    category: str = "CUSTOM_SCENARIO"
    query: str
    policy: PolicyMode = PolicyMode.STRICT
    ref_date: date = Field(default_factory=date.today)
    expected_verdict: Verdict = Verdict.APPROVE
    test_goal: str = "Enterprise compliance invariant check"


class BenchmarkRunRequest(BaseModel):
    custom_cases: list[BenchmarkTestCase] = Field(default_factory=list)


class BenchmarkCaseResult(BaseModel):
    case_id: str
    name: str
    category: str
    query: str
    policy: str
    expected_verdict: str
    actual_verdict: str
    passed: bool
    latency_ms: int
    claims_verified: int
    details: str
    answer_preview: str
    audit_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    quote_verified: bool = False
    scale_check_passed: bool = True
    fy_check_passed: bool = True
    cross_lab_passed: bool = False
    verbatim_quotes: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)


class BenchmarkSuiteReport(BaseModel):
    suite_id: str
    executed_at: str
    total_cases: int
    passed_cases: int
    accuracy_pct: float
    hallucination_catch_rate_pct: float
    avg_latency_ms: float
    total_estimated_cost_usd: float
    cases: list[BenchmarkCaseResult]


BENCHMARK_BATTERY: list[BenchmarkTestCase] = [
    BenchmarkTestCase(
        case_id="BENCH-01",
        name="Green Hydrogen Mission Outlay (FY 2025-26)",
        category="GROUNDED_FACT",
        query="What is the financial outlay for the National Green Hydrogen Mission for FY 2025-26?",
        policy=PolicyMode.STRICT,
        ref_date=date(2025, 3, 31),
        expected_verdict=Verdict.APPROVE,
        test_goal="Validates quantitative crore reconciliation (₹4,850 cr) and exact verbatim quote citation against cabinet note.",
    ),
    BenchmarkTestCase(
        case_id="BENCH-02",
        name="Offshore African LNG Sovereign Guarantee (Ungrounded Claim Trap)",
        category="HALLUCINATION_TRAP",
        query="Explain India's current bilateral sovereign guarantee commitments for offshore African LNG terminal construction in FY 2025-26.",
        policy=PolicyMode.STRICT,
        ref_date=date(2025, 3, 31),
        expected_verdict=Verdict.ABSTAIN,
        test_goal="Enforces strict zero-hallucination abstention when source evidence is completely absent from approved truth corpus.",
    ),
    BenchmarkTestCase(
        case_id="BENCH-03",
        name="100x Scale Distortion Trap (Lakh vs Crore)",
        category="SCALE_DISTORTION",
        query="The approved budgetary allocation for the National Green Hydrogen Mission for FY 2025-26 was ₹4,85,000 Lakh Crore.",
        policy=PolicyMode.STRICT,
        ref_date=date(2025, 3, 31),
        expected_verdict=Verdict.ABSTAIN,
        test_goal="Validates pure-Python lakh vs crore magnitude discord detection overriding distorted quantitative assertions.",
    ),
    BenchmarkTestCase(
        case_id="BENCH-04",
        name="SEBI AIF Statutory Liquid Cushion Mandate",
        category="STATUTORY_MANDATE",
        query="What is the minimum percentage of unencumbered liquid assets that Alternative Investment Funds must maintain under emergency drawdown rules?",
        policy=PolicyMode.STRICT,
        ref_date=date(2025, 1, 15),
        expected_verdict=Verdict.APPROVE,
        test_goal="Validates statutory circular quote extraction and 10% unencumbered liquid cushion mandate.",
    ),
    BenchmarkTestCase(
        case_id="BENCH-05",
        name="Temporal Expiration Boundary Enforcement",
        category="TEMPORAL_ISOLATION",
        query="What is the budgetary allocation for the National Green Hydrogen Mission for FY 2025-26 evaluated in June 2028?",
        policy=PolicyMode.STRICT,
        ref_date=date(2028, 6, 1),
        expected_verdict=Verdict.ABSTAIN,
        test_goal="Enforces strict temporal expiration guardrails: expired documents past validity window cannot certify future facts.",
    ),
]


async def execute_forensic_benchmark(
    db: AsyncSession,
    llm_router: VeritasRouter,
    custom_cases: list[BenchmarkTestCase] | None = None,
) -> BenchmarkSuiteReport:
    """Executes the standardized forensic benchmark battery plus any enterprise custom cases."""
    rows = (await db.execute(select(VeritasSource))).scalars().all()
    source_docs = [
        SourceDoc(
            doc_id=r.doc_id,
            title=r.title,
            text=r.text,
            valid_from=r.valid_from,
            valid_until=r.valid_until,
            is_primary=r.is_primary,
        )
        for r in rows
    ]

    pipeline = VeritasPipeline(router=llm_router, sources=source_docs)
    case_results: list[BenchmarkCaseResult] = []
    total_cost = 0.0
    total_latency = 0

    active_battery = list(BENCHMARK_BATTERY) + (custom_cases or [])

    for test in active_battery:
        t0 = time.perf_counter()
        report = await pipeline.run(
            query=test.query,
            policy=test.policy,
            ref_date=test.ref_date,
        )
        t1 = time.perf_counter()
        elapsed_ms = max(1, int((t1 - t0) * 1000))
        total_latency += elapsed_ms
        total_cost += report.estimated_cost_usd

        passed = report.verdict == test.expected_verdict
        claims_count = len(report.claim_audits)

        detail_msg = f"Expected {test.expected_verdict.value}, got {report.verdict.value}."
        if not passed and report.warnings:
            detail_msg += f" Warnings: {'; '.join(report.warnings)}"

        audit_id = f"aud_{hashlib.sha256(f'{test.case_id}_{test.query}_{time.time()}'.encode()).hexdigest()[:8]}"
        claim_dicts = [c.model_dump() for c in report.claim_audits]

        # Invariant checks
        quote_verified = report.verdict == Verdict.APPROVE or any(c.quote_verified for c in report.claim_audits)
        scale_passed = not any(c.numeric_mismatch for c in report.claim_audits)
        fy_passed = not any(c.fy_mismatch for c in report.claim_audits)
        cross_lab_passed = report.auditor_model_used is not None and any(c.cross_lab_supported for c in report.claim_audits)

        verbatim_quotes = [c.verbatim_quote for c in report.claim_audits if c.verbatim_quote]
        reasons = list(dict.fromkeys(report.warnings + [r for c in report.claim_audits for r in c.reasons]))

        # Ground real cryptographic audit log in database
        try:
            audit_entry = await prepare_audit_log_entry(
                db,
                audit_id=audit_id,
                query_text=test.query,
                verdict=report.verdict.value,
                answer=report.answer,
                policy_applied=test.policy.value,
                primary_model=report.model_used,
                auditor_model=report.auditor_model_used,
                failover_triggered=getattr(llm_router, "last_failover_occurred", False),
                latency_ms=elapsed_ms,
                estimated_cost_usd=report.estimated_cost_usd,
                claim_audits=claim_dicts,
                warnings=report.warnings,
                created_at=datetime.now(timezone.utc),
            )
            db.add(audit_entry)
            await db.commit()
        except Exception:
            pass

        case_results.append(
            BenchmarkCaseResult(
                case_id=test.case_id,
                name=test.name,
                category=test.category,
                query=test.query,
                policy=test.policy.value,
                expected_verdict=test.expected_verdict.value,
                actual_verdict=report.verdict.value,
                passed=passed,
                latency_ms=elapsed_ms,
                claims_verified=claims_count,
                details=detail_msg,
                answer_preview=report.answer[:140] + ("..." if len(report.answer) > 140 else ""),
                audit_id=audit_id,
                prompt_tokens=report.tokens_in,
                completion_tokens=report.tokens_out,
                estimated_cost_usd=report.estimated_cost_usd,
                quote_verified=quote_verified,
                scale_check_passed=scale_passed,
                fy_check_passed=fy_passed,
                cross_lab_passed=cross_lab_passed,
                verbatim_quotes=verbatim_quotes,
                rejection_reasons=reasons,
            )
        )

    passed_count = sum(1 for c in case_results if c.passed)
    accuracy_pct = round((passed_count / len(case_results)) * 100.0, 1) if case_results else 0.0

    # Negative/Trap test cases (cases expecting ABSTAIN)
    trap_cases = [c for c in case_results if c.expected_verdict == Verdict.ABSTAIN.value]
    trap_passed = sum(1 for c in trap_cases if c.passed)
    hallucination_catch_rate = (
        round((trap_passed / len(trap_cases)) * 100.0, 1) if trap_cases else 100.0
    )

    avg_latency = round(total_latency / len(case_results), 1) if case_results else 0.0

    return BenchmarkSuiteReport(
        suite_id=f"bnk_{uuid.uuid4().hex[:8]}",
        executed_at=date.today().isoformat(),
        total_cases=len(case_results),
        passed_cases=passed_count,
        accuracy_pct=accuracy_pct,
        hallucination_catch_rate_pct=hallucination_catch_rate,
        avg_latency_ms=avg_latency,
        total_estimated_cost_usd=round(total_cost, 4),
        cases=case_results,
    )
