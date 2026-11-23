import os
import urllib.request
import json
import sys

BASE_URL = os.getenv("VERITAS_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("VERITAS_API_KEY", "veritas-local-dev-key-2026")
headers = {"Content-Type": "application/json", "X-Veritas-Key": API_KEY}

def post(url, data):
    req = urllib.request.Request(BASE_URL + url, json.dumps(data).encode(), headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def get(url):
    req = urllib.request.Request(BASE_URL + url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

# 1. Register test source
src = post("/v1/sources", {
    "doc_id": "TEST-GROUNDED-01",
    "title": "Solar Subsidy Circular FY26",
    "text": "Solar subsidy budget for FY 2025-26 is fixed at Rs 150 crore across all states.",
    "valid_from": "2025-04-01",
    "valid_until": "2027-03-31",
    "is_primary": True
})
print("Registered source:", src["doc_id"])

# Case A: Grounded Query -> APPROVE
res_a = post("/v1/verify", {
    "query": "What is the solar subsidy budget for FY 2025-26?",
    "policy": "strict",
    "source_ids": ["TEST-GROUNDED-01"]
})
print("\n[Case A - Grounded Factual Query]:")
print("  Verdict:", res_a["verdict"])
print("  Answer:", res_a["answer"])
print("  Latency:", res_a["telemetry"]["latency_ms"], "ms")
print("  Cost USD: $", res_a["telemetry"]["estimated_cost_usd"])
print("  Numeric Concord:", res_a["telemetry"]["numeric_concord_pct"], "%")

# Case B: Conflicting Lakh/Crore Query -> ABSTAIN
res_b = post("/v1/verify", {
    "query": "Is the solar subsidy budget in FY 2025-26 set to Rs 150 lakh?",
    "policy": "strict",
    "source_ids": ["TEST-GROUNDED-01"]
})
print("\n[Case B - Conflicting Lakh vs Crore Query]:")
print("  Verdict:", res_b["verdict"])
print("  Answer:", res_b["answer"])
print("  Warnings:", res_b.get("warnings"))

# Case C: Out of Scope / Missing source -> ABSTAIN
res_c = post("/v1/verify", {
    "query": "What is the offshore equity holding in Cayman Islands?",
    "policy": "strict",
    "source_ids": ["TEST-GROUNDED-01"]
})
print("\n[Case C - Out-of-Scope / Uncited Query]:")
print("  Verdict:", res_c["verdict"])
print("  Answer:", res_c["answer"])

# Inspect persistence from DB
audits = get("/v1/audits?limit=5")
print("\n[Persistence Verification - Database Audit Records]:")
print("  Total recent audits in database:", len(audits))
for a in audits[:3]:
    print(f"  - [{a['audit_id']}] Query: '{a['query_text']}' | Verdict: {a['verdict']} | Latency: {a['latency_ms']}ms | Cost: ${a['estimated_cost_usd']}")
