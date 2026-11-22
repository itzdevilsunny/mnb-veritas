from __future__ import annotations

from app.gateway.registry import build_default_router
from app.gateway.router import VeritasRouter

_gateway: VeritasRouter | None = None


def get_gateway() -> VeritasRouter:
    """Process-wide gateway singleton (adapters, circuit-breaker state)."""
    global _gateway
    if _gateway is None:
        _gateway = build_default_router()
    return _gateway


get_veritas_router = get_gateway


async def close_gateway() -> None:
    global _gateway
    _gateway = None
