from __future__ import annotations

import pytest
from app.gateway.circuit_breaker import CircuitBreakerManager, CircuitState
from app.models.schemas import Lab


@pytest.mark.asyncio
async def test_circuit_breaker_initial_state_closed() -> None:
    cb = CircuitBreakerManager(failure_threshold=3, cooldown_seconds=1.0, redis_url="inmemory")
    state = await cb.get_state(Lab.ANTHROPIC)
    assert state == CircuitState.CLOSED
    assert await cb.can_execute(Lab.ANTHROPIC) is True


@pytest.mark.asyncio
async def test_circuit_breaker_trips_to_open_after_threshold() -> None:
    cb = CircuitBreakerManager(failure_threshold=2, cooldown_seconds=1.0, redis_url="inmemory")
    
    await cb.record_failure(Lab.OPENAI)
    state1 = await cb.get_state(Lab.OPENAI)
    assert state1 == CircuitState.CLOSED
    assert await cb.can_execute(Lab.OPENAI) is True

    await cb.record_failure(Lab.OPENAI)
    state2 = await cb.get_state(Lab.OPENAI)
    assert state2 == CircuitState.OPEN
    assert await cb.can_execute(Lab.OPENAI) is False


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_after_cooldown_and_recovery() -> None:
    import asyncio
    cb = CircuitBreakerManager(failure_threshold=1, cooldown_seconds=0.1, redis_url="inmemory")
    
    await cb.record_failure(Lab.GOOGLE)
    assert await cb.get_state(Lab.GOOGLE) == CircuitState.OPEN

    # Wait past cooldown
    await asyncio.sleep(0.15)
    assert await cb.get_state(Lab.GOOGLE) == CircuitState.HALF_OPEN
    assert await cb.can_execute(Lab.GOOGLE) is True

    # Record success -> recovers to CLOSED
    await cb.record_success(Lab.GOOGLE)
    assert await cb.get_state(Lab.GOOGLE) == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_manual_reset() -> None:
    cb = CircuitBreakerManager(failure_threshold=1, cooldown_seconds=10.0, redis_url="inmemory")
    await cb.record_failure(Lab.XAI)
    assert await cb.get_state(Lab.XAI) == CircuitState.OPEN

    await cb.reset(Lab.XAI)
    assert await cb.get_state(Lab.XAI) == CircuitState.CLOSED
    assert await cb.can_execute(Lab.XAI) is True


@pytest.mark.asyncio
async def test_circuit_breaker_all_status() -> None:
    cb = CircuitBreakerManager(failure_threshold=3, cooldown_seconds=5.0, redis_url="inmemory")
    status = await cb.get_all_status()
    assert "redis_connected" in status
    assert "providers" in status
    assert "anthropic" in status["providers"]
    assert status["providers"]["anthropic"]["state"] == "CLOSED"
