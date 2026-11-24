# MNB Veritas Python Client SDK & CLI

Official Python SDK and command-line interface (`veritas`) for **MNB Veritas** — evidence-gated verification middleware and forensic compliance workbench.

## Installation

```bash
pip install ./client
```

Or install in development editable mode:

```bash
pip install -e ./client
```

## Quickstart (CLI)

```bash
# Verify a claim with strict evidence gating
veritas verify "What is the capital outlay for the National Green Hydrogen Mission for FY 2025-26?" --policy strict

# Verify and export a cryptographically signed compliance certificate (PDF)
veritas verify "What is the policy repo rate for Q4 FY25?" --export-cert repo_rate_audit.pdf

# Check gateway circuits and provider availability
veritas health

# Verify SHA-256 tamper-evident audit ledger
veritas chain --json
```

## Quickstart (Python SDK)

### Async Client
```python
import asyncio
from veritas import VeritasClient, PolicyMode

async def main():
    async with VeritasClient(base_url="http://localhost:8000", api_key="vrt_live_...") as client:
        result = await client.verify(
            query="What is the approved budgetary allocation for FY 2025-26?",
            policy=PolicyMode.STRICT,
        )
        print(f"Verdict: {result.verdict}")
        print(f"Answer: {result.answer}")
        print(f"Audit ID: {result.audit_id}")

asyncio.run(main())
```

### Sync Client
```python
from veritas import VeritasSyncClient, PolicyMode

client = VeritasSyncClient(base_url="http://localhost:8000")
result = client.verify(
    query="What is the minimum unencumbered liquid cushion for AIFs?",
    policy=PolicyMode.STRICT,
)
print(result.verdict, result.answer)
client.close()
```

## Architecture

- **Zero Mock Execution:** Directly calls live FastAPI endpoints (`/v1/verify`, `/v1/health/providers`, `/v1/audits`).
- **5 Core Invariants:** Enforces verbatim quote character matches, lakh/crore scale checks, FY period boundary reconciliation, cross-lab auditor independence, and temporal expiration.
- **SHA-256 Merkle Chain:** Every verified synthesis produces a tamper-evident cryptographic hash record.
