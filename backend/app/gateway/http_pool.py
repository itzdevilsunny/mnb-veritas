from __future__ import annotations

import httpx

_shared_http_client: httpx.AsyncClient | None = None


def get_shared_http_client() -> httpx.AsyncClient:
    """
    Returns a pooled, application-wide httpx.AsyncClient.
    Configured with strict timeouts and connection limits:
      connect: 1.5s, read: 3.0s, write: 2.0s, pool: 2.0s.
    """
    global _shared_http_client
    if _shared_http_client is None or _shared_http_client.is_closed:
        timeout = httpx.Timeout(connect=1.5, read=3.0, write=2.0, pool=2.0)
        limits = httpx.Limits(max_keepalive_connections=30, max_connections=100)
        _shared_http_client = httpx.AsyncClient(timeout=timeout, limits=limits)
    return _shared_http_client


async def close_shared_http_client() -> None:
    """Closes the pooled httpx.AsyncClient during application shutdown."""
    global _shared_http_client
    if _shared_http_client is not None and not _shared_http_client.is_closed:
        await _shared_http_client.aclose()
        _shared_http_client = None
