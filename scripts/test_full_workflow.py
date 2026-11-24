#!/usr/bin/env python3
"""
MNB Veritas — Full Workflow Automated Verification Battery
Tests every subsystem: Health, Sources, PDF Upload, Standard Verify, Streaming Verify,
Temporal Expiration Guardrails, Forensic Benchmark Battery, and Audit Logging.
"""

from __future__ import annotations

import io
import json
import time
import urllib.request
import urllib.error
import pymupdf as fitz

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:3000"
API_KEY = "veritas-local-dev-key-2026"


def request(method: str, path: str, payload: dict | None = None, base: str = BASE_URL) -> tuple[int, dict | str]:
    url = f"{base}{path}"
    headers = {"Accept": "application/json", "X-Veritas-Key": API_KEY}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.getcode(), json.loads(raw)
            except Exception:
                return resp.getcode(), raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def create_sample_pdf(title: str, text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), f"OFFICIAL GAZETTE: {title}", fontsize=14)
    page.insert_text((72, 120), text, fontsize=10)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def upload_pdf_multipart(path: str, filename: str, pdf_bytes: bytes, fields: dict) -> tuple[int, dict | str]:
    boundary = "----VeritasBoundary7MA4YWxkTrZu0gW"
    body = bytearray()
    
    for k, v in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.extend(f"{v}\r\n".encode())
        
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    body.extend(b"Content-Type: application/pdf\r\n\r\n")
    body.extend(pdf_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Veritas-Key": API_KEY,
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.getcode(), json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def run_full_workflow():
    results = {}
    print("=" * 70)
    print("MNB VERITAS — COMPREHENSIVE FULL WORKFLOW AUDIT BATTERY")
    print("=" * 70)

    # 1. Health & Provider Status
    print("\n[PHASE 1] Checking Core Gateway & Provider Health...")
    s1, h1 = request("GET", "/health")
    assert s1 == 200, f"Health check failed: {h1}"
    print(f"  ✓ /health: OK ({h1.get('service')} v{h1.get('version')}, labs={h1.get('configured_labs')})")
    
    s2, h2 = request("GET", "/v1/health/providers")
    assert s2 == 200, f"Providers check failed: {h2}"
    active_count = h2.get("active_count", len(h2.get("providers", {})))
    total_configured = h2.get("total_configured", len(h2.get("providers", {})))
    print(f"  ✓ /v1/health/providers: {active_count}/{total_configured} providers active (Redis: {h2.get('redis_connected')}).")
    assert total_configured == 4, f"Expected 4 configured providers, got {total_configured}"
    results["phase1_health"] = f"{active_count}/{total_configured} ACTIVE"

    # 2. Source Corpus Lifecycle & PDF Ingestion
    print("\n[PHASE 2] Validating Truth Corpus Lifecycle & PDF Parsing...")
    pdf_text = "The Reserve Bank of India has revised the overnight Standing Deposit Facility (SDF) rate to 6.25 per cent effective January 2025."
    pdf_bytes = create_sample_pdf("RBI Monetary Policy Annexure", pdf_text)
    
    upload_fields = {
        "base_doc_id": "WF_TEST_PDF_01",
        "title": "RBI Monetary Policy Annexure (SDF 6.25%)",
        "valid_from": "2025-01-01",
        "valid_until": "2026-12-31",
        "is_primary": "true",
    }
    s3, up_resp = upload_pdf_multipart("/v1/sources/upload", "rbi_sdf_annexure.pdf", pdf_bytes, upload_fields)
    assert s3 == 201, f"PDF upload failed: {up_resp}"
    print(f"  ✓ /v1/sources/upload: Processed {up_resp.get('total_chunks')} chunk(s) across {up_resp.get('total_pages')} page(s).")
    results["phase2_ingestion"] = "PASSED"

    # 3. Standard Verification (Grounded Approval)
    print("\n[PHASE 3] Executing Standard Multi-Lab Verification (Grounded Approval)...")
    t0 = time.perf_counter()
    s4, v4 = request("POST", "/v1/verify", {
        "query": "What is the revised Standing Deposit Facility rate effective January 2025?",
        "policy": "standard",
        "reference_date": "2025-02-01",
    })
    elapsed4 = int((time.perf_counter() - t0) * 1000)
    assert s4 == 200, f"Verify failed: {v4}"
    assert v4["verdict"] in ["APPROVE", "QUALIFY"], f"Expected APPROVE or QUALIFY, got {v4['verdict']}"
    print(f"  ✓ Grounded Query: Verdict={v4['verdict']} | Latency={elapsed4}ms | Model={v4['telemetry']['primary_model']}")
    print(f"    Answer: {v4['answer'][:90]}...")
    results["phase3_verify_grounded"] = "PASSED"

    # 4. Real-Time Server-Sent Events (SSE) Streaming
    print("\n[PHASE 4] Executing Real-Time SSE Verification Streaming...")
    req_stream = urllib.request.Request(
        f"{BASE_URL}/v1/verify/stream",
        data=json.dumps({"query": "What is the capital expenditure outlay for FY 2025-26?", "policy": "strict"}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Veritas-Key": API_KEY, "Accept": "text/event-stream"},
        method="POST",
    )
    stages_seen = []
    with urllib.request.urlopen(req_stream, timeout=30) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if line.startswith("data:"):
                event = json.loads(line[5:].strip())
                if "stage" in event:
                    stages_seen.append(event["stage"])
                    print(f"  ✓ SSE Event: Stage {event.get('stage')} ({event.get('name')}) -> {event.get('message')}")
    assert 1 in stages_seen and 5 in stages_seen, f"Incomplete streaming stages: {stages_seen}"
    results["phase4_streaming"] = "PASSED"

    # 5. Temporal Validity & Hallucination Guardrails
    print("\n[PHASE 5] Enforcing Zero-Hallucination & Temporal Expiration Guardrails...")
    # 5a. Ungrounded claim trap
    s5a, v5a = request("POST", "/v1/verify", {
        "query": "What are India's bilateral commitments for offshore African LNG liquefaction terminals in FY 2025-26?",
        "policy": "strict",
        "reference_date": "2025-02-01",
    })
    assert s5a == 200 and v5a["verdict"] == "ABSTAIN", f"Expected ABSTAIN for ungrounded claim, got {v5a.get('verdict')}"
    print(f"  ✓ Hallucination Trap: Correctly ABSTAINED (Answer: '{v5a['answer']}')")

    # 5b. Temporal Expiration Guardrail
    s5b, v5b = request("POST", "/v1/verify", {
        "query": "What is the revised Standing Deposit Facility rate evaluated in December 2029?",
        "policy": "strict",
        "reference_date": "2029-12-01",
    })
    assert s5b == 200 and v5b["verdict"] == "ABSTAIN", f"Expected ABSTAIN for expired document, got {v5b.get('verdict')}"
    print(f"  ✓ Temporal Guardrail: Correctly ABSTAINED on expired document past validity window.")
    results["phase5_guardrails"] = "PASSED"

    # 6. Forensic Benchmark Suite Battery
    print("\n[PHASE 6] Running Forensic 5-Point Benchmark Battery...")
    t_bench = time.perf_counter()
    s6, b6 = request("POST", "/v1/benchmark/run", {})
    elapsed_bench = int((time.perf_counter() - t_bench) * 1000)
    assert s6 == 200, f"Benchmark suite failed: {b6}"
    print(f"  ✓ Benchmark Suite Completed: {b6['passed_cases']}/{b6['total_cases']} Passed ({b6['accuracy_pct']}%)")
    print(f"    Hallucination Trap Catch Rate: {b6['hallucination_catch_rate_pct']}% | Total Latency: {elapsed_bench}ms")
    results["phase6_benchmark"] = f"{b6['passed_cases']}/{b6['total_cases']} PASSED ({b6['accuracy_pct']}%)"

    # 7. Audit Trail & Forensic Persistence
    print("\n[PHASE 7] Auditing Append-Only Forensic Persistence...")
    s7, a7 = request("GET", "/v1/audits?limit=5")
    assert s7 == 200 and len(a7) > 0, f"Audit trail failed: {a7}"
    latest_audit = a7[0]
    print(f"  ✓ Audit Trail OK: {len(a7)} recent audits retrieved.")
    print(f"    Latest Audit ID: {latest_audit['audit_id']} | Verdict: {latest_audit['verdict']} | Cost: ${latest_audit['estimated_cost_usd']}")
    results["phase7_audit_trail"] = "PASSED"

    # 8. Frontend Next.js Proxy Integration
    print("\n[PHASE 8] Testing Frontend Dashboard Proxy Integration...")
    sf_root, _ = request("GET", "/", base=FRONTEND_URL)
    assert sf_root == 200, f"Frontend root check failed: {sf_root}"
    print(f"  ✓ Frontend [http://localhost:3000/]: HTTP 200 OK")

    sf_audits, fa_data = request("GET", "/api/audits", base=FRONTEND_URL)
    assert sf_audits == 200 and len(fa_data) > 0, f"Frontend audits proxy failed: {sf_audits}"
    print(f"  ✓ Frontend Proxy [/api/audits]: HTTP 200 OK ({len(fa_data)} items returned)")

    sf_sources, fs_data = request("GET", "/api/sources", base=FRONTEND_URL)
    assert sf_sources == 200 and len(fs_data) > 0, f"Frontend sources proxy failed: {sf_sources}"
    print(f"  ✓ Frontend Proxy [/api/sources]: HTTP 200 OK ({len(fs_data)} active sources)")
    results["phase8_frontend_proxy"] = "PASSED"

    # 9. Automated Database Cleanup of Test Fixtures
    print("\n[PHASE 9] Purging Synthetic Test Artifacts via Cleanup Route...")
    s9, c9 = request("DELETE", "/v1/sources/cleanup-test-data")
    assert s9 == 200, f"Cleanup failed: {c9}"
    print(f"  ✓ /v1/sources/cleanup-test-data: Removed {c9.get('deleted_sources_count')} test sources & {c9.get('deleted_audits_count')} test logs.")
    results["phase9_cleanup"] = "PASSED"

    print("\n" + "=" * 70)
    print("WORKFLOW BATTERY VERDICT: 100% OF PHASES PASSED CLEANLY")
    print("=" * 70)
    for phase, status in results.items():
        print(f"  • {phase:25}: {status}")
    print("=" * 70)


if __name__ == "__main__":
    run_full_workflow()
