from __future__ import annotations

import pytest
from app.gateway.circuit_breaker import get_circuit_breaker
from app.models.schemas import Lab


@pytest.fixture(autouse=True)
async def reset_circuit_breakers():
    """Ensures a clean circuit breaker state before and after each test."""
    cb = get_circuit_breaker()
    for lab in [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI]:
        await cb.reset(lab)
    yield
    for lab in [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI]:
        await cb.reset(lab)
