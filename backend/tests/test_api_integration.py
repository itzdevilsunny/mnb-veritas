from __future__ import annotations

import io
import json
from collections.abc import AsyncGenerator
from datetime import date
import pymupdf as fitz
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import get_db_session, get_veritas_router, router as veritas_router
from app.core.config import get_settings
from app.models.db import Base
from veritas_engine import Lab, MockProvider, VeritasRouter


def _build_sample_pdf_bytes(lines_per_page: list[list[str]]) -> bytes:
    """Creates an in-memory PDF for /v1/sources/upload endpoint tests."""
    doc = fitz.open()
    try:
        for page_lines in lines_per_page:
            page = doc.new_page(width=595, height=842)
            y = 72
            for line in page_lines:
                page.insert_text((72, y), line, fontsize=11)
                y += 22
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        doc.close()


@pytest_asyncio.fixture
async def test_app() -> AsyncGenerator[FastAPI, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI(title="MNB Veritas Integration Test App")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "mnb-veritas",
            "version": "1.4",
            "database": "connected",
            "configured_labs": ["anthropic", "openai", "google", "xai"],
        }

    app.include_router(veritas_router)

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    generator = MockProvider(
        Lab.ANTHROPIC,
        "claude-sonnet-5-5",
        json.dumps(
            {
                "draft_answer": "Approved grant allocation for FY 2025-26 is Rs 2.5 crore across 12 districts.",
                "claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "Approved grant allocation for FY 2025-26 is Rs 2.5 crore.",
                        "is_factual": True,
                        "verbatim_quote": "Approved grant allocation for FY 2025-26 is Rs 2.5 crore",
                        "cited_doc_id": "CIRC-2026-01",
                    }
                ],
            }
        ),
    )
    auditor = MockProvider(
        Lab.GOOGLE,
        "gemini-4-hydrogen",
        json.dumps({"supported": True, "reason": "Exact match in source."}),
    )
    mock_router = VeritasRouter({Lab.ANTHROPIC: generator, Lab.GOOGLE: auditor})

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_veritas_router] = lambda: mock_router

    yield app

    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=test_app)
    dev_key = get_settings().VERITAS_API_KEY
    headers = {"X-Veritas-Key": dev_key}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as ac:
        yield ac


@pytest.mark.integration
async def test_health_endpoint(client: httpx.AsyncClient) -> None:
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "mnb-veritas"
    assert "database" in data
    assert "configured_labs" in data


@pytest.mark.integration
async def test_providers_health_and_reset(client: httpx.AsyncClient) -> None:
    res = await client.get("/v1/health/providers")
    assert res.status_code == 200
    data = res.json()
    assert "redis_connected" in data
    assert "providers" in data
    assert "anthropic" in data["providers"]
    assert data["providers"]["anthropic"]["state"] == "CLOSED"

    # Reset valid lab
    reset_res = await client.post("/v1/health/providers/anthropic/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "ok"

    # Reset invalid lab
    bad_reset = await client.post("/v1/health/providers/invalid_lab/reset")
    assert bad_reset.status_code == 400


@pytest.mark.integration
async def test_sources_lifecycle(client: httpx.AsyncClient) -> None:
    payload = {
        "doc_id": "CIRC-2026-01",
        "title": "FY 2025-26 Grant Circular",
        "text": "Approved grant allocation for FY 2025-26 is Rs 2.5 crore across 12 districts.",
        "valid_from": "2025-04-01",
        "valid_until": "2027-03-31",
        "is_primary": True,
    }
    create_res = await client.post("/v1/sources", json=payload)
    assert create_res.status_code in (200, 201)
    assert create_res.json()["doc_id"] == "CIRC-2026-01"

    list_res = await client.get("/v1/sources")
    assert list_res.status_code == 200
    assert any(item["doc_id"] == "CIRC-2026-01" for item in list_res.json())

    expiry_res = await client.patch(
        "/v1/sources/CIRC-2026-01/expiry",
        json={"valid_until": "2026-12-31"},
    )
    assert expiry_res.status_code == 200
    assert expiry_res.json()["valid_until"] == "2026-12-31"

    del_res = await client.delete("/v1/sources/CIRC-2026-01")
    assert del_res.status_code in (200, 204)


@pytest.mark.integration
async def test_verify_and_audits_flow(client: httpx.AsyncClient) -> None:
    # First seed a source
    payload = {
        "doc_id": "CIRC-2026-01",
        "title": "FY 2025-26 Grant Circular",
        "text": "Approved grant allocation for FY 2025-26 is Rs 2.5 crore across 12 districts.",
        "valid_from": "2025-04-01",
        "valid_until": "2027-03-31",
        "is_primary": True,
    }
    await client.post("/v1/sources", json=payload)

    # 1. Grounded verify
    v_res = await client.post(
        "/v1/verify",
        json={
            "query": "What is the grant allocation for FY 2025-26?",
            "policy": "strict",
            "source_ids": ["CIRC-2026-01"],
        },
    )
    assert v_res.status_code == 200
    data = v_res.json()
    assert data["verdict"] == "APPROVE"
    assert "2.5 crore" in data["answer"]
    assert data["telemetry"]["primary_model"].startswith("anthropic:")

    # 2. Audit list inspection
    audit_res = await client.get("/v1/audits?limit=5")
    assert audit_res.status_code == 200
    audits = audit_res.json()
    assert len(audits) >= 1
    assert audits[0]["verdict"] == "APPROVE"


@pytest.mark.integration
async def test_pdf_upload_chunking(client: httpx.AsyncClient) -> None:
    pdf_bytes = _build_sample_pdf_bytes(
        [
            ["Ministry of Finance Notification 2026.", "Total capital outlay is ₹5,000 crore."],
            ["Component II guidelines.", "Eligible entities will receive 15% subsidy."],
        ]
    )

    files = {"file": ("test_doc.pdf", pdf_bytes, "application/pdf")}
    data = {
        "base_doc_id": "TEST-PDF-01",
        "title": "Ministry Notification 2026",
        "valid_from": "2026-01-01",
        "valid_until": "2027-12-31",
        "is_primary": "true",
    }

    res = await client.post("/v1/sources/upload", files=files, data=data)
    assert res.status_code == 201, f"Status {res.status_code}, Body: {res.text}"
    body = res.json()
    assert body["base_doc_id"] == "TEST-PDF-01"
    assert body["total_pages"] == 2
    assert body["chunks_created"] >= 2


@pytest.mark.integration
async def test_forensic_benchmark_suite_endpoint(client: httpx.AsyncClient) -> None:
    res = await client.post("/v1/benchmark/run")
    assert res.status_code == 200, f"Status {res.status_code}, Body: {res.text}"
    report = res.json()
    assert "suite_id" in report
    assert report["total_cases"] == 5
    assert report["hallucination_catch_rate_pct"] == 100.0
    assert len(report["cases"]) == 5
