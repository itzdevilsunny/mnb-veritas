from __future__ import annotations

import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import get_db_session, get_veritas_router, router as veritas_router
from app.core.auth_rate_limit import RedisRateLimiter, rate_limiter
from app.core.config import get_settings
from app.models.db import Base
from veritas_engine import Lab, MockProvider, VeritasRouter


@pytest_asyncio.fixture
async def auth_test_app() -> FastAPI:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI(title="Auth & Rate Limit Test App")
    app.include_router(veritas_router)

    async def _override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_veritas_router] = lambda: VeritasRouter({})

    # Reset rate limiter memory buckets
    rate_limiter.reset_in_memory()

    yield app

    await engine.dispose()


@pytest.mark.asyncio
async def test_missing_api_key_returns_401(auth_test_app: FastAPI):
    transport = httpx.ASGITransport(app=auth_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/v1/sources")
        assert res.status_code == 401
        assert "Missing" in res.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_api_key_returns_401(auth_test_app: FastAPI):
    transport = httpx.ASGITransport(app=auth_test_app)
    headers = {"X-Veritas-Key": "invalid_bogus_token_12345"}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as client:
        res = await client.get("/v1/sources")
        assert res.status_code == 401
        assert "Invalid or revoked" in res.json()["detail"]


@pytest.mark.asyncio
async def test_valid_dev_admin_key_authenticates(auth_test_app: FastAPI):
    transport = httpx.ASGITransport(app=auth_test_app)
    admin_key = get_settings().VERITAS_API_KEY
    headers = {"X-Veritas-Key": admin_key}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as client:
        res = await client.get("/v1/sources")
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_create_and_use_per_app_api_key(auth_test_app: FastAPI):
    transport = httpx.ASGITransport(app=auth_test_app)
    admin_key = get_settings().VERITAS_API_KEY
    admin_headers = {"X-Veritas-Key": admin_key}

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Create a per-app API key
        create_res = await client.post(
            "/v1/app-keys",
            headers=admin_headers,
            json={"app_name": "portal-service", "rate_limit_per_minute": 10},
        )
        assert create_res.status_code == 201
        key_data = create_res.json()
        raw_key = key_data["raw_key"]
        key_id = key_data["id"]
        assert raw_key.startswith("vrt_live_")
        assert key_data["app_name"] == "portal-service"

        # 2. Use the new app key to access endpoints
        app_headers = {"X-Veritas-Key": raw_key}
        use_res = await client.get("/v1/sources", headers=app_headers)
        assert use_res.status_code == 200

        # 3. Revoke the key
        del_res = await client.delete(f"/v1/app-keys/{key_id}", headers=admin_headers)
        assert del_res.status_code == 204

        # 4. Accessing with revoked key returns 401
        revoked_res = await client.get("/v1/sources", headers=app_headers)
        assert revoked_res.status_code == 401


@pytest.mark.asyncio
async def test_rate_limiting_enforcement_returns_429_with_retry_after(auth_test_app: FastAPI):
    transport = httpx.ASGITransport(app=auth_test_app)
    admin_key = get_settings().VERITAS_API_KEY
    admin_headers = {"X-Veritas-Key": admin_key}

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create a key with strict limit of 3 requests/min
        create_res = await client.post(
            "/v1/app-keys",
            headers=admin_headers,
            json={"app_name": "rate-limited-app", "rate_limit_per_minute": 3},
        )
        assert create_res.status_code == 201
        raw_key = create_res.json()["raw_key"]
        app_headers = {"X-Veritas-Key": raw_key}

        # 3 requests pass
        for _ in range(3):
            r = await client.get("/v1/sources", headers=app_headers)
            assert r.status_code == 200

        # 4th request exceeds quota -> 429
        breach_res = await client.get("/v1/sources", headers=app_headers)
        assert breach_res.status_code == 429
        assert "Retry-After" in breach_res.headers
        assert int(breach_res.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_isolated():
    limiter = RedisRateLimiter(redis_url="inmemory")
    key_id = "test_key_abc"

    # Limit = 2
    ok1, count1, retry1 = await limiter.check_rate_limit(key_id, limit_per_minute=2)
    assert ok1 is True
    assert count1 == 1

    ok2, count2, retry2 = await limiter.check_rate_limit(key_id, limit_per_minute=2)
    assert ok2 is True
    assert count2 == 2

    # Exceed limit
    ok3, count3, retry3 = await limiter.check_rate_limit(key_id, limit_per_minute=2)
    assert ok3 is False
    assert count3 == 3
    assert retry3 > 0
