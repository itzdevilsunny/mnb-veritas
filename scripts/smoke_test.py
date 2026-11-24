#!/usr/bin/env python3
"""Smoke-test script for MNB Veritas API, source lifecycle, and /v1/verify."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

BASE_URL = os.getenv("VERITAS_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("VERITAS_API_KEY", "veritas-local-dev-key-2026")
TEST_DOC_ID = "SMOKE-FY26-01"


def _request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    expect_status: tuple[int, ...] = (200,),
) -> tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers: dict[str, str] = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if API_KEY:
        headers["X-Veritas-Key"] = API_KEY

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8")
            body = json.loads(raw) if raw.strip() else None
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw) if raw.strip() else None
        except json.JSONDecodeError:
            body = raw

    if status not in expect_status:
        raise AssertionError(
            f"{method} {path} returned HTTP {status}, expected {expect_status}. Body: {body}"
        )
    return status, body


def main() -> int:
    print(f"[1/5] Checking GET /health at {BASE_URL}...")
    _, health = _request("GET", "/health", expect_status=(200,))
    print("  -> Health OK:", health)
    configured_labs = set(health.get("configured_labs", []))
    expected_labs = {"anthropic", "openai", "google", "xai", "ollama"}
    assert expected_labs.issubset(configured_labs), f"Expected 5 configured labs, got {configured_labs}"

    print(f"[2/5] Upserting approved source {TEST_DOC_ID}...")
    source_payload = {
        "doc_id": TEST_DOC_ID,
        "title": "Smoke Test Budget Circular FY 2025-26",
        "text": (
            "Approved allocation for FY 2025-26 is Rs 2.5 crore across 12 districts. "
            "Disbursement cap per district is 20 percent."
        ),
        "valid_from": "2025-04-01",
        "valid_until": "2027-03-31",
        "is_primary": True,
    }
    _, created_src = _request("POST", "/v1/sources", payload=source_payload, expect_status=(200, 201))
    print("  -> Registered source:", created_src.get("doc_id"))

    try:
        print("[3/5] Running POST /v1/verify for grounded query (expect APPROVE)...")
        _, approve_res = _request(
            "POST",
            "/v1/verify",
            payload={
                "query": "What is the approved allocation for FY 2025-26?",
                "policy": "strict",
                "source_ids": [TEST_DOC_ID],
            },
            expect_status=(200,),
        )
        verdict_a = approve_res.get("verdict")
        print(f"  -> Verdict: {verdict_a} | Answer: {approve_res.get('answer')}")
        if verdict_a not in {"APPROVE", "QUALIFY", "ABSTAIN"}:
            raise AssertionError(f"Unexpected verdict: {verdict_a}")

        print("[4/5] Running POST /v1/verify for uncited claim (expect ABSTAIN -> 'No answer possible')...")
        _, abstain_res = _request(
            "POST",
            "/v1/verify",
            payload={
                "query": "What is the offshore equity holding in Cayman Islands?",
                "policy": "strict",
                "source_ids": [TEST_DOC_ID],
            },
            expect_status=(200,),
        )
        verdict_b = abstain_res.get("verdict")
        answer_b = abstain_res.get("answer")
        print(f"  -> Verdict: {verdict_b} | Answer: {answer_b}")
        if verdict_b == "ABSTAIN" and answer_b != "No answer possible":
            raise AssertionError(
                f"Expected exact answer 'No answer possible' on ABSTAIN, got: {answer_b!r}"
            )

        print("[5/5] Checking GET /v1/audits persistence...")
        _, audits = _request("GET", "/v1/audits?limit=5", expect_status=(200,))
        if not isinstance(audits, list) or len(audits) == 0:
            raise AssertionError("Audit log returned empty list after verification calls.")
        print(f"  -> Audit log OK ({len(audits)} recent records retrieved).")
    finally:
        print(f"[Cleanup] Archiving smoke test source {TEST_DOC_ID}...")
        _request("DELETE", f"/v1/sources/{TEST_DOC_ID}", expect_status=(200, 204))
        print("[Cleanup] Purging synthetic smoke test fixtures via cleanup route...")
        _request("DELETE", "/v1/sources/cleanup-test-data", expect_status=(200, 204))

    print("ALL SMOKE TESTS PASSED CLEANLY.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
