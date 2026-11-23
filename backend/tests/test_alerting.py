from __future__ import annotations

import pytest
from app.services.alerting import dispatch_compliance_alert, send_test_webhook


@pytest.mark.asyncio
async def test_dispatch_compliance_alert_no_url_returns_false() -> None:
    res = await dispatch_compliance_alert(
        event_type="VERDICT_ABSTAIN",
        audit_id="aud_test123",
        query_text="Test ungrounded query",
        verdict="ABSTAIN",
        policy_applied="strict",
        reasons=["Source expired"],
        model="mock:deterministic",
        webhook_url=None,
    )
    assert res is False


@pytest.mark.asyncio
async def test_send_test_webhook_unreachable_target() -> None:
    # Testing graceful failure on unreachable host
    success, msg = await send_test_webhook("http://127.0.0.1:59999/nonexistent-webhook")
    assert success is False
    assert len(msg) > 0
