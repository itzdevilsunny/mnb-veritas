from __future__ import annotations

import logging
from app.gateway.moe_router import MoERoute
from app.gateway.router import VeritasRouter
from app.models.schemas import Lab
from app.pipeline.jsonutil import parse_json_object

logger = logging.getLogger("veritas.pipeline.s3_examine_llm")


async def audit_claim_with_cross_lab_model(
    router: VeritasRouter,
    claim_text: str,
    verbatim_quote: str,
    generator_lab: Lab,
) -> tuple[bool, str, str | None]:
    """
    Stage 3B: Cross-Lab Secondary Model Audit via MoE Deep Audit Expert.
    Ensures an independent model from a distinct lab verifies semantic entailment.
    Returns: (is_supported, reason, auditor_model_string)
    """
    auditor_chain = router.get_auditor_chain(generator_lab)
    if not auditor_chain:
        return False, "No distinct secondary lab available or configured for cross-lab auditing.", None

    system_prompt = (
        "You are an independent compliance auditor from a separate AI lab. "
        "Your task is to verify if the claim is strictly entailed by the verbatim quote. "
        "Reply ONLY in JSON: {\"supported\": true|false, \"reason\": str}."
    )
    user_prompt = f"Claim: {claim_text}\nVerbatim Quote: {verbatim_quote}"

    try:
        raw, provider, _ = await router.call_cross_lab_concurrent(
            candidate_labs=auditor_chain,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            excluded_labs={generator_lab},
        )
        parsed = parse_json_object(raw)
        supported = bool(parsed.get("supported", False))
        reason = parsed.get("reason", "Entailment verified.")
        auditor_str = f"{provider.lab.value}:{provider.model}"
        return supported, reason, auditor_str
    except Exception as exc:
        logger.warning("Zero-PII Telemetry: Cross-lab audit failed across secondary chain %s: %s", auditor_chain, exc)
        return False, f"Cross-lab auditor from distinct lab unreachable or exhausted: {exc}", None

