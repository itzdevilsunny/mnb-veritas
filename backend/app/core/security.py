from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable
from fastapi import Header, HTTPException, status

from app.core.auth_rate_limit import (
    AuthenticatedClient,
    RedisRateLimiter,
    generate_app_key,
    hash_api_key,
    rate_limiter,
    verify_authenticated_client,
)
from app.core.config import get_settings


def verify_api_key(
    provided: str | None,
    allowed_hashes: Iterable[str] | None = None,
) -> bool:
    """
    Constant-time API key verification.
    If allowed_hashes is provided, checks provided key against the collection of hashes.
    If allowed_hashes is omitted, checks against configured VERITAS_API_KEY.
    """
    if not provided or not str(provided).strip():
        return False
    digest = hash_api_key(provided)
    if allowed_hashes is not None:
        ok = False
        for allowed in allowed_hashes:
            ok |= hmac.compare_digest(digest, allowed.strip().lower())
        return ok
    settings = get_settings()
    if settings.VERITAS_API_KEY:
        return hmac.compare_digest(provided.strip(), settings.VERITAS_API_KEY.strip())
    return True


require_api_key = verify_authenticated_client

__all__ = [
    "AuthenticatedClient",
    "RedisRateLimiter",
    "generate_app_key",
    "hash_api_key",
    "rate_limiter",
    "require_api_key",
    "verify_api_key",
    "verify_authenticated_client",
]
