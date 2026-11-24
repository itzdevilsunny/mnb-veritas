from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.models.db import VeritasAppKey

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

logger = logging.getLogger("veritas.auth")


def hash_api_key(raw_key: str) -> str:
    """Computes SHA-256 hash of API key for safe storage and lookup."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def generate_app_key(app_name: str, rate_limit: int = 60) -> tuple[str, str, str]:
    """Generates a secure random API key, its prefix, and SHA-256 hash."""
    token = secrets.token_hex(24)
    raw_key = f"vrt_live_{token}"
    key_prefix = raw_key[:12]
    key_hash = hash_api_key(raw_key)
    return raw_key, key_prefix, key_hash


@dataclass
class AuthenticatedClient:
    app_name: str
    key_prefix: str
    key_hash: str
    rate_limit_per_minute: int
    is_admin: bool = False
    allowed_policies: list[str] = field(default_factory=lambda: ["standard", "balanced", "strict"])


class RedisRateLimiter:
    """
    Fixed-window per-minute rate limiter backed by Redis with zero-latency
    in-memory sliding dictionary fallback.
    """

    def __init__(self, redis_url: str = "redis://127.0.0.1:6379/0") -> None:
        self.redis_url = redis_url
        self._redis_client: Any | None = None
        self._memory_counts: dict[str, int] = {}
        self._memory_expiry: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._redis_disabled = redis_url.lower() == "inmemory"
        self._last_redis_fail: float = 0.0

    async def _get_redis(self) -> Any | None:
        if self._redis_disabled or aioredis is None:
            return None
        now = time.monotonic()
        if now - self._last_redis_fail < 30.0:
            return None
        if self._redis_client is None:
            try:
                self._redis_client = aioredis.from_url(
                    self.redis_url,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                    decode_responses=True,
                )
                await self._redis_client.ping()
            except Exception:
                self._last_redis_fail = now
                self._redis_client = None
                return None
        return self._redis_client

    async def check_rate_limit(
        self, key_identifier: str, limit_per_minute: int
    ) -> tuple[bool, int, int]:
        """
        Increments request counter for current minute window.
        Returns: (allowed, current_count, retry_after_seconds)
        """
        now = time.time()
        minute_window = int(now // 60)
        retry_after = max(1, 60 - int(now % 60))
        bucket_key = f"veritas:ratelimit:{key_identifier}:{minute_window}"

        # 1. Attempt Redis increment
        redis = await self._get_redis()
        if redis is not None:
            try:
                pipe = redis.pipeline()
                pipe.incr(bucket_key)
                pipe.expire(bucket_key, 90)
                results = await pipe.execute()
                current_count = int(results[0])
                allowed = current_count <= limit_per_minute
                return allowed, current_count, retry_after
            except Exception as e:
                logger.debug("Redis rate limit failed, falling back to in-memory: %s", e)
                self._last_redis_fail = time.monotonic()
                self._redis_client = None

        # 2. In-memory fallback
        async with self._lock:
            # Clean expired windows
            cutoff = now - 90.0
            expired_keys = [k for k, exp in self._memory_expiry.items() if exp < cutoff]
            for k in expired_keys:
                self._memory_counts.pop(k, None)
                self._memory_expiry.pop(k, None)

            current_count = self._memory_counts.get(bucket_key, 0) + 1
            self._memory_counts[bucket_key] = current_count
            self._memory_expiry[bucket_key] = now + 90.0

            allowed = current_count <= limit_per_minute
            return allowed, current_count, retry_after

    def reset_in_memory(self) -> None:
        """Helper for unit tests."""
        self._memory_counts.clear()
        self._memory_expiry.clear()


# Global rate limiter singleton
_settings = get_settings()
rate_limiter = RedisRateLimiter(redis_url=_settings.REDIS_URL)


async def verify_authenticated_client(
    x_veritas_key: str | None = Header(default=None, alias="X-Veritas-Key"),
    db: AsyncSession = Depends(get_db_session),
) -> AuthenticatedClient:
    """
    Validates X-Veritas-Key header using constant-time comparison against:
    1. System master/fallback key (VERITAS_API_KEY)
    2. Per-app SHA-256 hashed API keys in database
    Applies per-key rate limiting (429 with Retry-After on quota breach).
    """
    settings = get_settings()
    expected_dev_key = settings.VERITAS_API_KEY

    if not x_veritas_key or not x_veritas_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required X-Veritas-Key header",
        )

    clean_key = x_veritas_key.strip()
    key_hash = hash_api_key(clean_key)
    client: AuthenticatedClient | None = None

    # Check 1: Fallback / Admin Dev Key
    if expected_dev_key and hmac.compare_digest(clean_key, expected_dev_key.strip()):
        client = AuthenticatedClient(
            app_name="admin-dev",
            key_prefix=clean_key[:12],
            key_hash=key_hash,
            rate_limit_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            is_admin=True,
        )

    # Check 2: Per-App SHA-256 Hashed Keys
    if client is None:
        stmt = select(VeritasAppKey).where(
            VeritasAppKey.sha256_hash == key_hash,
            VeritasAppKey.is_active == True,
        )
        app_record = (await db.execute(stmt)).scalar_one_or_none()

        if app_record is not None and hmac.compare_digest(app_record.sha256_hash, key_hash):
            app_record.last_used_at = datetime.now(timezone.utc)
            await db.commit()
            client = AuthenticatedClient(
                app_name=app_record.app_name,
                key_prefix=app_record.key_prefix,
                key_hash=app_record.sha256_hash,
                rate_limit_per_minute=app_record.rate_limit_per_minute,
                is_admin=False,
                allowed_policies=app_record.allowed_policies or ["standard", "balanced", "strict"],
            )

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked Veritas API key",
        )

    # Rate Limiting Check
    allowed, count, retry_after = await rate_limiter.check_rate_limit(
        client.key_hash, client.rate_limit_per_minute
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Quota: {client.rate_limit_per_minute} requests/minute",
            headers={"Retry-After": str(retry_after)},
        )

    return client
