from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import date
from typing import Any
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import get_db_session, get_veritas_router, router as veritas_router
from app.core.config import get_settings
from app.models.db import Base, VeritasAuditLog, VeritasSource
from tests.mocks import MockProvider
from veritas_engine import Lab, VeritasRouter


@pytest_asyncio.fixture
async def batch_app() -> AsyncGenerator[tuple[FastAPI, async_sessionmaker[AsyncSession]], None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI(title="MNB Veritas Option C Test App")
    app.include_router(veritas_router)

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    generator = MockProvider(
        Lab.ANTHROPIC,
        "claude-sonnet-5-5",
        json.dumps(
            {
                "draft_answer": "Capital expenditure outlay stands at Rs 11,11,111 crore for FY 2025-26.",
                "claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "Capital expenditure outlay stands at Rs 11,11,111 crore for FY 2025-26.",
                        "is_factual": True,
                        "verbatim_quote": "Total capital expenditure outlay stands at Rs 11,11,111 crore for FY 2025-26.",
                        "cited_doc_id": "doc_budget_2025",
                    }
                ],
            }
        ),
    )
    auditor = MockProvider(
        Lab.GOOGLE,
        "gemini-flash-latest",
        json.dumps({"supported": True, "reason": "Exact match in source doc."}),
    )
    mock_router = VeritasRouter({Lab.ANTHROPIC: generator, Lab.GOOGLE: auditor})

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_veritas_router] = lambda: mock_router

    # Seed an initial source doc
    async with session_factory() as db:
        src = VeritasSource(
            doc_id="doc_budget_2025",
            title="Union Budget 2025-26",
            text="Total capital expenditure outlay stands at Rs 11,11,111 crore for FY 2025-26. MNRE quarterly reviews begin Q1 FY26.",
            valid_from=date(2025, 1, 1),
            valid_until=date(2026, 3, 31),
            is_primary=True,
            is_active=True,
            authority_tier="statutory",
        )
        db.add(src)
        await db.commit()

    yield app, session_factory

    await engine.dispose()


@pytest_asyncio.fixture
async def client(batch_app: tuple[FastAPI, async_sessionmaker[AsyncSession]]) -> AsyncGenerator[httpx.AsyncClient, None]:
    app, _ = batch_app
    transport = httpx.ASGITransport(app=app)
    dev_key = get_settings().VERITAS_API_KEY
    headers = {"X-Veritas-Key": dev_key}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as ac:
        yield ac


@pytest.mark.asyncio
async def test_batch_verify_size_limits(client: httpx.AsyncClient) -> None:
    # 1. Empty items list fails validation (min_length=1)
    res_empty = await client.post("/v1/verify/batch", json={"items": []})
    assert res_empty.status_code == 422

    # 2. Exceeding max_length=50 fails validation
    oversized = [{"query": f"Query {i}", "item_id": f"q_{i}"} for i in range(51)]
    res_over = await client.post("/v1/verify/batch", json={"items": oversized})
    assert res_over.status_code == 422


@pytest.mark.asyncio
async def test_batch_verify_scoped_policy_forbidden(
    client: httpx.AsyncClient,
    batch_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    # Create an app key restricted to "standard" only
    res_key = await client.post(
        "/v1/app-keys",
        json={"app_name": "StandardOnlyApp", "allowed_policies": ["standard"]},
    )
    assert res_key.status_code == 201
    raw_key = res_key.json()["raw_key"]

    app, _ = batch_app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-Veritas-Key": raw_key},
    ) as restricted_client:
        # Request a batch with policy="strict" -> 403 Forbidden
        res_forbidden = await restricted_client.post(
            "/v1/verify/batch",
            json={
                "items": [{"query": "What is capex outlay for FY 2025-26?", "policy": "strict"}],
                "policy": "standard",
            },
        )
        assert res_forbidden.status_code == 403
        assert "is restricted to policy profiles" in res_forbidden.json()["detail"]


@pytest.mark.asyncio
async def test_batch_verify_execution_and_summary(client: httpx.AsyncClient) -> None:
    payload = {
        "items": [
            {"item_id": "item-1", "query": "What is the capital expenditure outlay for FY 2025-26?"},
            {"item_id": "item-2", "query": "What is the capital expenditure outlay for FY 2025-26?", "policy": "standard"},
        ],
        "policy": "strict",
        "concurrency_limit": 2,
    }
    res = await client.post("/v1/verify/batch", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "summary" in data
    assert "results" in data
    summary = data["summary"]
    assert summary["total_items"] == 2
    assert summary["error_count"] == 0
    assert summary["total_latency_ms"] >= 0
    assert len(data["results"]) == 2
    assert data["results"][0]["item_id"] == "item-1"
    assert data["results"][0]["success"] is True
    assert data["results"][1]["item_id"] == "item-2"
    assert data["results"][1]["success"] is True


@pytest.mark.asyncio
async def test_sequential_audit_chain_and_tamper_detection(
    client: httpx.AsyncClient,
    batch_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    _, session_factory = batch_app

    # 1. Run two separate single queries
    await client.post("/v1/verify", json={"query": "Query one for audit chain", "policy": "standard"})
    await client.post("/v1/verify", json={"query": "Query two for audit chain", "policy": "standard"})

    # 2. Check DB records for sequential prev_hash -> record_hash linkage
    async with session_factory() as db:
        stmt = select(VeritasAuditLog).order_by(VeritasAuditLog.created_at.asc())
        rows = (await db.execute(stmt)).scalars().all()
        assert len(rows) >= 2

        # First record must have prev_hash == "GENESIS"
        assert rows[0].prev_hash == "GENESIS"
        assert rows[0].record_hash is not None

        # Each subsequent record must link to the previous record's record_hash
        for i in range(1, len(rows)):
            assert rows[i].prev_hash == rows[i - 1].record_hash
            assert rows[i].record_hash is not None

    # 3. Call GET /v1/audits/verify-chain
    res_chain = await client.get("/v1/audits/verify-chain")
    assert res_chain.status_code == 200
    chain_data = res_chain.json()
    assert chain_data["valid"] is True
    assert chain_data["checked_count"] == len(rows)
    assert chain_data["first_broken_audit_id"] is None
    assert chain_data["latest_record_hash"] == rows[-1].record_hash

    # 4. Tamper with a record in DB to simulate malicious alteration
    tampered_id = rows[0].audit_id
    async with session_factory() as db:
        record_to_tamper = (
            await db.execute(select(VeritasAuditLog).where(VeritasAuditLog.audit_id == tampered_id))
        ).scalar_one()
        # Mutate the verdict from its original value to "QUALIFY"
        record_to_tamper.verdict = "QUALIFY"
        await db.commit()

    # 5. Re-run GET /v1/audits/verify-chain and assert tampering is detected
    res_tampered = await client.get("/v1/audits/verify-chain")
    assert res_tampered.status_code == 200
    tampered_data = res_tampered.json()
    assert tampered_data["valid"] is False
    assert tampered_data["first_broken_audit_id"] == tampered_id
    assert "recomputed hash" in tampered_data["details"]


@pytest.mark.asyncio
async def test_concurrent_audit_writes_preserve_chain_integrity(
    batch_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    _, session_factory = batch_app
    import uuid
    from app.services.audit_chain import write_audit_log, verify_audit_chain_integrity

    async def _write_entry(i: int) -> None:
        async with session_factory() as session:
            await write_audit_log(
                db=session,
                audit_id=f"aud_stress_{i:04d}_{uuid.uuid4().hex[:6]}",
                query_text=f"Concurrent stress assertion #{i}",
                verdict="APPROVE",
                answer=f"Verified result #{i}",
                policy_applied="strict",
                primary_model="anthropic:claude-sonnet-4-6",
                auditor_model="openai:gpt-4o",
                failover_triggered=False,
                latency_ms=50,
                estimated_cost_usd=0.001,
                claim_audits=[{"claim_id": f"c_{i}", "verdict": "APPROVE"}],
                warnings=[],
            )

    # Launch 10 concurrent writes
    await asyncio.gather(*[_write_entry(i) for i in range(10)])

    # Verify that the chain is valid and all entries are strictly linked
    async with session_factory() as session:
        report = await verify_audit_chain_integrity(session)
        assert report["valid"] is True
        assert report["checked_count"] >= 10
        assert report["first_broken_audit_id"] is None

