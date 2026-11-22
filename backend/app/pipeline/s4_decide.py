from __future__ import annotations

from app.models.schemas import ClaimAuditResult, ExtractionBundle, PolicyMode, Verdict

NO_ANSWER_POSSIBLE = "No answer possible"


def evaluate_policy_verdict(
    bundle: ExtractionBundle,
    audits: list[ClaimAuditResult],
    policy: PolicyMode,
    has_valid_sources: bool,
) -> tuple[Verdict, str, list[str]]:
    """
    Stage 4: Hard-Coded Policy Engine.
    Enforces deterministic abstention without LLM overrides.
    """
    warnings: list[str] = []
    factual_audits = [a for a in audits if a.is_factual]

    # Invariant 4: If no valid source or no factual audits present, ABSTAIN
    if not has_valid_sources or not factual_audits:
        return (
            Verdict.ABSTAIN,
            NO_ANSWER_POSSIBLE,
            ["No valid approved source backing for factual claims."],
        )

    for a in factual_audits:
        # Number or FY contradictions
        if a.numeric_mismatch or a.fy_mismatch:
            if policy == PolicyMode.STRICT:
                return Verdict.ABSTAIN, NO_ANSWER_POSSIBLE, a.reasons
            return Verdict.ABSTAIN, NO_ANSWER_POSSIBLE, a.reasons

        # Uncited or missing verbatim quote
        if not a.quote_verified or not a.cross_lab_supported:
            return Verdict.ABSTAIN, NO_ANSWER_POSSIBLE, a.reasons

        if a.source_expired:
            warnings.extend(a.reasons)

    # If any sources were expired but quotes matched
    if warnings:
        if policy == PolicyMode.STRICT:
            return Verdict.ABSTAIN, NO_ANSWER_POSSIBLE, warnings
        return (
            Verdict.QUALIFY,
            f"{bundle.draft_answer}\n\n[Temporal Caveat: {' | '.join(warnings)}]",
            warnings,
        )

    return Verdict.APPROVE, bundle.draft_answer, warnings
