from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
import httpx

from app.core.config import get_settings

logger = logging.getLogger("veritas.alerting")


async def dispatch_compliance_alert(
    event_type: str,
    audit_id: str,
    query_text: str,
    verdict: str,
    policy_applied: str,
    reasons: list[str],
    model: str,
    webhook_url: str | None = None,
) -> bool:
    """Dispatches a structured compliance alert to the configured corporate webhook."""
    settings = get_settings()
    target_url = webhook_url or settings.COMPLIANCE_WEBHOOK_URL
    if not target_url:
        return False

    now_iso = datetime.now(timezone.utc).isoformat()
    reason_bullets = "\n".join(f"• {r}" for r in reasons) if reasons else "• Strict invariant mismatch"

    payload: dict[str, Any] = {
        "text": f"🚨 [MNB Veritas] Verification Alert: {audit_id} triggered {verdict}",
        "event_type": event_type,
        "audit_id": audit_id,
        "verdict": verdict,
        "policy": policy_applied,
        "query": query_text,
        "reasons": reasons,
        "model": model,
        "timestamp": now_iso,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 Regulatory Invariant Alert: {verdict}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Audit ID:*\n`{audit_id}`"},
                    {"type": "mrkdwn", "text": f"*Policy:*\n`{policy_applied.upper()}`"},
                    {"type": "mrkdwn", "text": f"*Model:*\n`{model}`"},
                    {"type": "mrkdwn", "text": f"*Timestamp:*\n{now_iso}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Query:*\n_{query_text}_\n\n*Violations / Caveats:*\n{reason_bullets}",
                },
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(target_url, json=payload)
            if resp.status_code in {200, 204}:
                logger.info("Compliance alert dispatched for audit %s", audit_id)
                return True
            logger.warning(
                "Webhook responded with %d: %s", resp.status_code, resp.text[:200]
            )
            return False
    except Exception as e:
        logger.error("Failed to dispatch compliance alert: %s", e)
        return False


async def send_test_webhook(webhook_url: str) -> tuple[bool, str]:
    """Sends a verification ping to the user-supplied webhook URL."""
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "text": "✅ [MNB Veritas] Webhook test ping successful. Regulatory alerting channel active.",
        "event_type": "TEST_PING",
        "timestamp": now_iso,
        "service": "MNB Veritas Multi-Lab Governance Engine",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code in {200, 204}:
                return True, "Ping delivered successfully (HTTP 200/204)"
            return False, f"Remote server returned HTTP {resp.status_code}: {resp.text[:120]}"
    except Exception as e:
        return False, str(e)
