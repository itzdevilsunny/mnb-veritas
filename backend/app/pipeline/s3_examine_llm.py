from __future__ import annotations

import logging
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
    Stage 3B: Cross-Lab Secondary Model Audit.
    Ensures an independent model verifies semantic entailment.
    Returns: (is_supported, reason, auditor_model_string)
    """
    auditor_chain = router.get_auditor_chain(generator_lab)
    if not auditor_chain:
        return True, "No distinct secondary lab available; skipped cross-model check.", None

    system_prompt = (
        "You are an independent compliance auditor from a separate AI lab. "
        "Your task is to verify if the claim is strictly entailed by the verbatim quote. "
        "Reply ONLY in JSON: {\"supported\": true|false, \"reason\": str}."
    )
    user_prompt = f"Claim: {claim_text}\nVerbatim Quote: {verbatim_quote}"

    try:
        raw, provider, _ = await router.call_with_failover(
            auditor_chain, system_prompt, user_prompt
        )
        parsed = parse_json_object(raw)
        supported = bool(parsed.get("supported", False))
        reason = parsed.get("reason", "Entailment verified.")
        auditor_str = f"{provider.lab.value}:{provider.model}"
        return supported, reason, auditor_str
    except Exception as exc:
        return False, f"Cross-lab audit error: {exc}", None
