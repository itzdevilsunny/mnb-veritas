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
        # Number or FY contradictions always force abstention across all policies
        if a.numeric_mismatch or a.fy_mismatch:
            return Verdict.ABSTAIN, NO_ANSWER_POSSIBLE, a.reasons

        # Uncited or missing verbatim quote always forces abstention
        if not a.quote_verified:
            return Verdict.ABSTAIN, NO_ANSWER_POSSIBLE, a.reasons or ["Uncited or missing verbatim quote in approved sources."]

        # Cross-lab audit check:
        # - STRICT: Mandatory. If secondary lab unconfirmed or unavailable -> ABSTAIN ("No answer possible")
        # - BALANCED: If unconfirmed -> flag with qualification caveat
        # - STANDARD: Cross-lab audit is optional; single-lab verified quote approved
        if not a.cross_lab_supported:
            if policy == PolicyMode.STRICT:
                return Verdict.ABSTAIN, NO_ANSWER_POSSIBLE, a.reasons or ["Cross-lab audit could not independently verify claim."]
            elif policy == PolicyMode.BALANCED:
                warnings.append("Cross-lab audit unconfirmed or unavailable from secondary lab.")

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

    # Invariant: Critical claims in STRICT mode escalate for mandatory compliance sign-off
    if policy == PolicyMode.STRICT:
        critical_audits = [a for a in factual_audits if getattr(a, "is_critical", False)]
        if critical_audits:
            crit_reasons = ["Critical regulatory claim requires compliance officer sign-off before publication."]
            return (
                Verdict.ESCALATE,
                f"{bundle.draft_answer}\n\n[ESCALATED FOR HUMAN REVIEW: Compliance officer sign-off required.]",
                crit_reasons,
            )

    return Verdict.APPROVE, bundle.draft_answer, warnings
