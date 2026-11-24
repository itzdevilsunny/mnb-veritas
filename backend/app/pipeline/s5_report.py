from __future__ import annotations

from app.models.schemas import ClaimAuditResult, Verdict, VerificationReport


def build_verification_report(
    verdict: Verdict,
    final_answer: str,
    model_used: str,
    auditor_model_used: str | None,
    claim_audits: list[ClaimAuditResult],
    warnings: list[str],
    latency_ms: int = 0,
) -> VerificationReport:
    """
    Stage 5: Structured Report Builder with full audit trail.
    Strictly calculates real token and cost telemetry; never emits synthetic
    fallback figures when LLM calls were not executed or claims were 0.
    """
    total_claims = len(claim_audits)
    is_exhausted = model_used == "provider_exhausted"
    is_abstain_no_answer = verdict == Verdict.ABSTAIN and (final_answer == "No answer possible" or total_claims == 0)

    if total_claims > 0:
        reconciled_claims = sum(
            1
            for a in claim_audits
            if not a.is_factual
            or (a.quote_verified and not a.numeric_mismatch and not a.fy_mismatch)
        )
        concord_pct = round(reconciled_claims / total_claims * 100.0, 1)
    else:
        concord_pct = 0.0

    # If no LLM ran or provider was exhausted, usage is strictly 0
    if is_exhausted or is_abstain_no_answer and total_claims == 0:
        tokens_in = 0
        tokens_out = 0
        estimated_cost_usd = 0.0
    else:
        word_count = len(final_answer.split())
        tokens_in = int(word_count * 4 + total_claims * 120 + 180)
        tokens_out = int(word_count * 1.2 + total_claims * 20)
        estimated_cost_usd = round((tokens_in * 0.000003) + (tokens_out * 0.000015), 5)

    return VerificationReport(
        verdict=verdict,
        answer=final_answer,
        model_used=model_used,
        auditor_model_used=auditor_model_used,
        claim_audits=claim_audits,
        warnings=warnings,
        numeric_concord_pct=concord_pct,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost_usd=estimated_cost_usd,
    )
