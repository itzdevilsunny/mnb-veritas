from __future__ import annotations

from datetime import date
from app.gateway.adapters import (
    AnthropicProvider,
    GeminiProvider,
    MockProvider,
    OpenAICompatProvider,
)
from app.gateway.base import LLMProvider
from app.gateway.router import VeritasRouter
from app.models.schemas import (
    ClaimAuditResult,
    ExtractionBundle,
    ExtractedClaim,
    Lab,
    PolicyMode,
    SourceDoc,
    Verdict,
    VerificationReport,
)
from app.pipeline.s1_extract import extract_claims, strip_fences
from app.pipeline.s2_retrieve import retrieve_relevant_sources
from app.pipeline.s3_examine_code import (
    UNIT_MULTIPLIERS,
    check_numeric_and_fy_consistency,
    extract_fy_tokens,
    extract_scaled_quantities,
    normalize_text,
    verify_verbatim_quote,
)
from app.pipeline.s3_examine_llm import audit_claim_with_cross_lab_model
from app.pipeline.s4_decide import NO_ANSWER_POSSIBLE, evaluate_policy_verdict
from app.pipeline.s5_report import build_verification_report


class VeritasPipeline:
    """
    Layer 2: The 5-Stage Veritas Verification Engine.
    Coordinates Extract -> Retrieve -> Examine (Code & Cross-Lab) -> Decide -> Report.
    """

    NO_ANSWER = NO_ANSWER_POSSIBLE

    def __init__(self, router: VeritasRouter, sources: list[SourceDoc]) -> None:
        self.router = router
        self.sources_by_id: dict[str, SourceDoc] = {s.doc_id: s for s in sources}

    async def run(
        self,
        query: str,
        policy: PolicyMode = PolicyMode.STRICT,
        preferred_labs: list[Lab] | None = None,
        ref_date: date | None = None,
        source_ids: list[str] | None = None,
    ) -> VerificationReport:
        today = ref_date or date.today()
        labs = preferred_labs or [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI]

        # Stage 2: Retrieve & filter temporal validity
        valid_docs, expired_docs = retrieve_relevant_sources(
            sources=list(self.sources_by_id.values()),
            query=query,
            ref_date=today,
            source_ids=source_ids,
        )
        candidate_docs = valid_docs or expired_docs

        # Stage 1: Extract atomic factual claims
        bundle, gen_provider, failover = await extract_claims(
            self.router, query, candidate_docs, labs
        )

        # Stage 3: Examine (Deterministic Code + Cross-Lab Secondary LLM)
        auditor_model_used: str | None = None
        audits: list[ClaimAuditResult] = []

        for claim in bundle.claims:
            if not claim.is_factual:
                audits.append(
                    ClaimAuditResult(
                        claim_id=claim.claim_id,
                        claim_text=claim.claim_text,
                        is_factual=False,
                        quote_verified=True,
                        cross_lab_supported=True,
                        matched_doc_id=claim.cited_doc_id,
                        verbatim_quote=claim.verbatim_quote,
                    )
                )
                continue

            doc = self.sources_by_id.get(claim.cited_doc_id or "")
            reasons: list[str] = []

            if not doc:
                audits.append(
                    ClaimAuditResult(
                        claim_id=claim.claim_id,
                        claim_text=claim.claim_text,
                        is_factual=True,
                        quote_verified=False,
                        reasons=["No valid cited_doc_id matched an approved truth source."],
                    )
                )
                continue

            expired = not doc.is_valid_on(today)
            if expired:
                reasons.append(
                    f"Source {doc.doc_id} expired on {doc.valid_until} (checked against {today})."
                )

            # Invariant 1: Exact verbatim substring match
            quote_ok = verify_verbatim_quote(claim.verbatim_quote, doc.text)
            if not quote_ok:
                reasons.append("Verbatim quote missing or not an exact character match in source.")

            # Invariant 2: Deterministic Python financial & FY validation
            num_bad, fy_bad, num_reasons = check_numeric_and_fy_consistency(
                claim.claim_text, claim.verbatim_quote or ""
            )
            reasons.extend(num_reasons)

            # Query-to-Claim Invariant Checks:
            # Check FY agreement between user query and claim
            q_fy = extract_fy_tokens(query)
            c_fy = extract_fy_tokens(claim.claim_text)
            if q_fy and c_fy and q_fy != c_fy:
                fy_bad = True
                reasons.append(
                    f"Query requested FY {sorted(q_fy)}, but claim references {sorted(c_fy)}"
                )

            # Check scaled quantitative agreement between user query and claim
            q_quants = [v for v, u in extract_scaled_quantities(query) if u == "base_number"]
            c_quants = [v for v, u in extract_scaled_quantities(claim.claim_text) if u == "base_number"]
            if q_quants and c_quants:
                for q_val in q_quants:
                    if not any(abs(q_val - c_val) <= 1e-5 * max(1.0, abs(c_val)) for c_val in c_quants):
                        num_bad = True
                        reasons.append(
                            f"Query queried quantity {q_val:g} contradicts verified claim quantity {[round(x, 2) for x in c_quants]}"
                        )

            # Invariant 3: Cross-Lab Secondary Model Audit
            cross_lab_ok = False
            if quote_ok and not num_bad and not fy_bad:
                cross_lab_ok, audit_reason, audit_model = await audit_claim_with_cross_lab_model(
                    self.router, claim.claim_text, claim.verbatim_quote or "", gen_provider.lab
                )
                if audit_model:
                    auditor_model_used = audit_model
                if not cross_lab_ok:
                    reasons.append(f"Cross-lab audit rejected: {audit_reason}")

            # Extract page / chunk index from metadata if available
            meta = doc.metadata or {}
            page_num = meta.get("page_number")
            chunk_idx = meta.get("chunk_index")

            audits.append(
                ClaimAuditResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    is_factual=True,
                    quote_verified=quote_ok,
                    source_expired=expired,
                    numeric_mismatch=num_bad,
                    fy_mismatch=fy_bad,
                    cross_lab_supported=cross_lab_ok,
                    reasons=reasons,
                    matched_doc_id=doc.doc_id,
                    verbatim_quote=claim.verbatim_quote,
                    page_number=page_num,
                    chunk_index=chunk_idx,
                )
            )

        # Stage 4: Decide
        verdict, final_answer, warnings = evaluate_policy_verdict(
            bundle=bundle,
            audits=audits,
            policy=policy,
            has_valid_sources=bool(valid_docs),
        )

        # Stage 5: Report
        return build_verification_report(
            verdict=verdict,
            final_answer=final_answer,
            model_used=f"{gen_provider.lab.value}:{gen_provider.model}",
            auditor_model_used=auditor_model_used,
            claim_audits=audits,
            warnings=warnings,
        )

    async def run_stream(
        self,
        query: str,
        policy: PolicyMode = PolicyMode.STRICT,
        preferred_labs: list[Lab] | None = None,
        ref_date: date | None = None,
        source_ids: list[str] | None = None,
    ):
        """
        Server-Sent Events (SSE) generator yielding real-time progress events for each verification stage.
        """
        import json
        today = ref_date or date.today()
        labs = preferred_labs or [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI]

        # Stage 1: Retrieval
        valid_docs, expired_docs = retrieve_relevant_sources(
            sources=list(self.sources_by_id.values()),
            query=query,
            ref_date=today,
            source_ids=source_ids,
        )
        candidate_docs = valid_docs or expired_docs
        yield {
            "stage": 1,
            "name": "RETRIEVAL",
            "message": f"Retrieved {len(candidate_docs)} candidate regulatory documents ({len(valid_docs)} active, {len(expired_docs)} expired).",
            "progress": 25,
        }

        # Stage 2: Claim Extraction
        bundle, gen_provider, failover = await extract_claims(
            self.router, query, candidate_docs, labs
        )
        yield {
            "stage": 2,
            "name": "EXTRACTION",
            "message": f"Extracted {len(bundle.claims)} claims using {gen_provider.lab.value}:{gen_provider.model}.",
            "progress": 50,
        }

        # Stage 3: Deterministic & Cross-Lab Examination
        auditor_model_used: str | None = None
        audits: list[ClaimAuditResult] = []

        for claim in bundle.claims:
            if not claim.is_factual:
                audits.append(
                    ClaimAuditResult(
                        claim_id=claim.claim_id,
                        claim_text=claim.claim_text,
                        is_factual=False,
                        quote_verified=True,
                        cross_lab_supported=True,
                        matched_doc_id=claim.cited_doc_id,
                        verbatim_quote=claim.verbatim_quote,
                    )
                )
                continue

            doc = self.sources_by_id.get(claim.cited_doc_id or "")
            reasons: list[str] = []

            if not doc:
                audits.append(
                    ClaimAuditResult(
                        claim_id=claim.claim_id,
                        claim_text=claim.claim_text,
                        is_factual=True,
                        quote_verified=False,
                        reasons=["No valid cited_doc_id matched an approved truth source."],
                    )
                )
                continue

            expired = not doc.is_valid_on(today)
            if expired:
                reasons.append(
                    f"Source {doc.doc_id} expired on {doc.valid_until} (checked against {today})."
                )

            quote_ok = verify_verbatim_quote(claim.verbatim_quote, doc.text)
            if not quote_ok:
                reasons.append("Verbatim quote missing or not an exact character match in source.")

            num_bad, fy_bad, num_reasons = check_numeric_and_fy_consistency(
                claim.claim_text, claim.verbatim_quote or ""
            )
            reasons.extend(num_reasons)

            cross_lab_ok = False
            if quote_ok and not num_bad and not fy_bad:
                cross_lab_ok, audit_reason, audit_model = await audit_claim_with_cross_lab_model(
                    self.router, claim.claim_text, claim.verbatim_quote or "", gen_provider.lab
                )
                if audit_model:
                    auditor_model_used = audit_model
                if not cross_lab_ok:
                    reasons.append(f"Cross-lab audit rejected: {audit_reason}")

            meta = doc.metadata or {}
            audits.append(
                ClaimAuditResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    is_factual=True,
                    quote_verified=quote_ok,
                    source_expired=expired,
                    numeric_mismatch=num_bad,
                    fy_mismatch=fy_bad,
                    cross_lab_supported=cross_lab_ok,
                    reasons=reasons,
                    matched_doc_id=doc.doc_id,
                    verbatim_quote=claim.verbatim_quote,
                    page_number=meta.get("page_number"),
                    chunk_index=meta.get("chunk_index"),
                )
            )

        yield {
            "stage": 3,
            "name": "AUDIT",
            "message": f"Deterministic code verified {sum(1 for a in audits if a.quote_verified)} quotes; cross-lab auditor: {auditor_model_used or 'Single Lab'}.",
            "progress": 75,
        }

        # Stage 4: Decision & Policy Evaluation
        verdict, final_answer, warnings = evaluate_policy_verdict(
            bundle=bundle,
            audits=audits,
            policy=policy,
            has_valid_sources=bool(valid_docs),
        )

        yield {
            "stage": 4,
            "name": "DECISION",
            "message": f"Applied {policy.value.upper()} policy -> Verdict: {verdict.value}.",
            "progress": 90,
        }

        # Stage 5: Compilation
        report = build_verification_report(
            verdict=verdict,
            final_answer=final_answer,
            model_used=f"{gen_provider.lab.value}:{gen_provider.model}",
            auditor_model_used=auditor_model_used,
            claim_audits=audits,
            warnings=warnings,
        )

        yield {
            "stage": 5,
            "name": "COMPLETE",
            "message": "Verification report generated successfully.",
            "progress": 100,
            "report": report.model_dump(),
        }


__all__ = [
    "Lab",
    "PolicyMode",
    "Verdict",
    "SourceDoc",
    "ExtractedClaim",
    "ExtractionBundle",
    "ClaimAuditResult",
    "VerificationReport",
    "LLMProvider",
    "MockProvider",
    "AnthropicProvider",
    "OpenAICompatProvider",
    "GeminiProvider",
    "VeritasRouter",
    "VeritasPipeline",
    "normalize_text",
    "verify_verbatim_quote",
    "extract_scaled_quantities",
    "extract_fy_tokens",
    "check_numeric_and_fy_consistency",
    "UNIT_MULTIPLIERS",
    "strip_fences",
]
