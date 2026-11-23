from __future__ import annotations

import json
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "veritas-local-dev-key-2026"


def verify_query(query: str, ref_date: str = "2025-06-01", policy: str = "strict") -> dict:
    url = f"{BASE_URL}/v1/verify"
    payload = {
        "query": query,
        "policy": policy,
        "reference_date": ref_date,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Veritas-Key": API_KEY,
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_latest_audit(limit: int = 1) -> dict:
    url = f"{BASE_URL}/v1/audits?limit={limit}"
    req = urllib.request.Request(
        url,
        headers={"X-Veritas-Key": API_KEY, "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data[0] if data else {}


def main():
    print("=" * 80)
    print("MNB VERITAS — LIVE WORKBENCH ADVERSARIAL & NUMERIC STRESS BATTERY")
    print("=" * 80)

    battery = [
        {
            "id": "CASE-1",
            "title": "Scale Unit Mismatch (Lakh vs. Crore - 100x Scale Distortion)",
            "query": "Is the total capital expenditure outlay ₹11,11,111 lakh for FY 2025-26 under the Union Budget?",
            "expected_verdict": "ABSTAIN",
            "invariant": "Invariant 2 (Deterministic Numeric Scale Verification)",
        },
        {
            "id": "CASE-2",
            "title": "Financial Year (FY) Boundary Mismatch (FY 2026-27 vs. FY 2025-26)",
            "query": "What is the financial outlay ear-marked specifically for FY 2026-27 pilot electrolysers under the Green Hydrogen Mission?",
            "expected_verdict": "ABSTAIN",
            "invariant": "Invariant 2 (FY Token Extraction & Rejection)",
        },
        {
            "id": "CASE-3",
            "title": "Hallucinated / Invented Quantitative Figure",
            "query": "What is the bilateral sovereign credit guarantee facility of ₹500 crore for offshore African LNG liquefaction terminals?",
            "expected_verdict": "ABSTAIN",
            "invariant": "Invariant 1 & 2 (No Uncited Figures / Zero Hallucination)",
        },
        {
            "id": "CASE-4",
            "title": "Strict Grounded Entailment (Grounded Approval)",
            "query": "What is the approved capital expenditure outlay for FY 2025-26 under the Union Budget?",
            "expected_verdict": "APPROVE",
            "invariant": "All 3 Invariants (Verbatim Quote + Numeric Concord + Cross-Lab)",
        },
    ]

    for item in battery:
        print(f"\n[{item['id']}] {item['title']}")
        print(f"  • Query            : \"{item['query']}\"")
        print(f"  • Invariant Tested : {item['invariant']}")
        
        t0 = time.perf_counter()
        res = verify_query(item["query"])
        elapsed = int((time.perf_counter() - t0) * 1000)
        
        verdict = res.get("verdict")
        answer = res.get("answer")
        telemetry = res.get("telemetry", {})
        claims = res.get("claim_audits", [])
        
        print(f"  • Response Verdict : {verdict} (Expected: {item['expected_verdict']})")
        print(f"  • Latency          : {elapsed}ms | Engine: {telemetry.get('primary_model')} | Auditor: {telemetry.get('auditor_model')}")
        print(f"  • Output Answer    : \"{answer}\"")
        
        if claims:
            print("  • Claim Forensic Details:")
            for c in claims:
                print(f"    - Claim ID      : {c.get('claim_id')}")
                print(f"    - Quote Verified: {c.get('quote_verified')}")
                print(f"    - Numeric Ok    : {not c.get('numeric_mismatch')}")
                print(f"    - FY Ok         : {not c.get('fy_mismatch')}")
                print(f"    - Cross-Lab Ok  : {c.get('cross_lab_supported')}")
                if c.get("reasons"):
                    print(f"    - Rejection Reasons : {c.get('reasons')}")
        else:
            print("  • Claim Forensic Details: 0 claims admitted (Direct Pipeline Abstention)")

        # Fetch recorded audit entry
        audit = get_latest_audit(1)
        if audit and audit.get("query_text") == item["query"]:
            print(f"  • Persistent Audit : ID={audit.get('audit_id')} | Policy={audit.get('policy_applied')} | SafeToPublish={audit.get('verdict') == 'APPROVE'}")

        assert verdict == item["expected_verdict"], f"Expected {item['expected_verdict']}, got {verdict}"
        print(f"  ✓ {item['id']} PASSED")

    print("\n" + "=" * 80)
    print("ALL 4 ADVERSARIAL & NUMERIC STRESS TESTS PASSED WITH 100% INVARIANT ENFORCEMENT")
    print("=" * 80)


if __name__ == "__main__":
    main()
