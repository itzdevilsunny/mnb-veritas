from __future__ import annotations

import logging
from app.gateway.base import LLMProvider
from app.gateway.router import VeritasRouter
from app.models.schemas import ExtractionBundle, Lab, SourceDoc
from app.pipeline.jsonutil import parse_json_object, strip_fences

logger = logging.getLogger("veritas.pipeline.s1_extract")


async def extract_claims(
    router: VeritasRouter,
    query: str,
    candidate_docs: list[SourceDoc],
    preferred_labs: list[Lab],
) -> tuple[ExtractionBundle, LLMProvider, bool]:
    """
    Stage 1: Extract atomic factual claims and candidate verbatim quotes from approved sources.
    """
    context_block = "\n\n".join(
        f"[DOC_ID: {d.doc_id} | VALID: {d.valid_from} to {d.valid_until or 'open'}]\n{d.text}"
        for d in candidate_docs
    )
    system_prompt = (
        "You are an evidence-grounded extraction engine for MNB Veritas. "
        "Use ONLY the approved sources provided. Do not invent, extrapolate, or guess. "
        "For every factual claim, extract an atomic sentence, copy the exact verbatim substring "
        "from the source text into `verbatim_quote`, and specify `cited_doc_id`. "
        "If a claim is not backed by the sources, set `verbatim_quote` to null. "
        "Respond STRICTLY in JSON format matching: {\"draft_answer\": str, \"claims\": ["
        "{\"claim_id\": str, \"claim_text\": str, \"is_factual\": bool, \"is_critical\": bool, "
        "\"verbatim_quote\": str|null, \"cited_doc_id\": str|null}]}."
        "If a claim involves statutory capital thresholds, sovereign guarantees, or critical regulatory mandates, set is_critical to true."
    )
    user_prompt = f"Question: {query}\n\nApproved Sources:\n{context_block or 'NONE'}"
    raw, provider, failover = await router.call_with_failover(
        preferred_labs, system_prompt, user_prompt
    )
    try:
        parsed = parse_json_object(raw)
        return ExtractionBundle.model_validate(parsed), provider, failover
    except Exception as exc:
        logger.warning("Failed to parse JSON from %s output: %s. Raw: %s", provider.model, exc, raw[:200])
        # Return empty extraction bundle safely
        return ExtractionBundle(draft_answer="No answer possible", claims=[]), provider, failover
