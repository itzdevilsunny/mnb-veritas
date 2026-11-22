"""Keyless demo of the whole pipeline using mocked labs.

    cd backend && python scripts/demo_offline.py
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gateway.circuit_breaker import ProviderCircuitBreaker  # noqa: E402
from app.gateway.mock import MockAdapter  # noqa: E402
from app.gateway.router import MultiLabGateway  # noqa: E402
from app.models.schemas import Lab, PolicyMode, SourceDoc  # noqa: E402
from app.pipeline.orchestrator import VeritasPipeline  # noqa: E402

SOURCE = SourceDoc(
    "SRC-001", "Annual Filing FY 2025-26",
    "Total verified grant allocation for FY 2025-26 stood at Rs 2.5 crore across 12 districts.",
    date(2025, 4, 1), date(2027, 3, 31),
)


def claude_says(claim_text: str, quote: str | None, doc: str | None) -> str:
    return json.dumps({"draft_answer": claim_text, "claims": [
        {"claim_id": "c1", "claim_text": claim_text, "is_factual": True, "verbatim_quote": quote, "cited_doc_id": doc}]})


async def case(title: str, generator_json: str, query: str) -> None:
    gw = MultiLabGateway(
        {Lab.ANTHROPIC: MockAdapter(Lab.ANTHROPIC, "claude-sonnet-5-5", generator_json),
         Lab.GOOGLE: MockAdapter(Lab.GOOGLE, "gemini-4-hydrogen", json.dumps({"supported": True, "reason": "ok"}))},
        ProviderCircuitBreaker(redis_url="inmemory"),
    )
    r = await VeritasPipeline(gw, [SOURCE]).run(query, PolicyMode.STRICT, ref_date=date(2026, 11, 22))
    print(f"\n== {title}\n   verdict: {r.verdict.value}\n   answer : {r.answer}")
    for w in r.warnings:
        print(f"   note   : {w}")


async def main() -> None:
    q = "What was the grant allocation for FY 2025-26?"
    quote = "Total verified grant allocation for FY 2025-26 stood at Rs 2.5 crore"
    await case("Grounded claim", claude_says("Grant allocation for FY 2025-26 was Rs 2.5 crore.", quote, "SRC-001"), q)
    await case("Hallucinated amount (no quote)", claude_says("Grant allocation for FY 2025-26 was Rs 90 crore.", None, None), q)
    await case("Wrong unit: 25 crore vs 2.5 crore", claude_says("Grant allocation for FY 2025-26 was Rs 25 crore.", quote, "SRC-001"), q)
    await case("Wrong year: FY 2026-27", claude_says("Grant allocation for FY 2026-27 was Rs 2.5 crore.", quote, "SRC-001"), q)


if __name__ == "__main__":
    asyncio.run(main())
