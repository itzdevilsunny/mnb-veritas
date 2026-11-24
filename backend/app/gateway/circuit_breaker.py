from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

from app.core.config import get_settings
from app.models.schemas import Lab

logger = logging.getLogger("veritas.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerManager:
    """
    Manages Circuit Breaker states (CLOSED, OPEN, HALF_OPEN) for multi-lab LLM providers.
    Uses Redis when available, with automatic transparent fallback to an in-memory async store.
    """

    def __init__(
        self,
        failure_threshold: int = 2,
        cooldown_seconds: float = 15.0,
        redis_url: str | None = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.redis_url = redis_url if redis_url is not None else get_settings().REDIS_URL
        self._redis: aioredis.Redis | None = None
        self._redis_connected: bool = False
        self._last_redis_attempt: float = 0.0
        self._redis_retry_interval: float = 15.0

        # In-memory fallback storage
        self._local_states: dict[str, dict[str, Any]] = {
            lab.value: {
                "state": CircuitState.CLOSED.value,
                "failure_count": 0,
                "last_failure_time": 0.0,
            }
            for lab in [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI, Lab.OLLAMA]
        }

    async def _get_redis(self) -> aioredis.Redis | None:
        if not aioredis or not self.redis_url or self.redis_url.startswith("inmemory"):
            return None

        if self._redis is not None:
            return self._redis

        now = time.time()
        # Back off if recent connection attempt failed
        if not self._redis_connected and (now - self._last_redis_attempt < self._redis_retry_interval):
            return None

        self._last_redis_attempt = now
        try:
            client = aioredis.from_url(
                self.redis_url,
                socket_timeout=0.5,
                socket_connect_timeout=0.5,
                decode_responses=True,
            )
            await client.ping()
            self._redis = client
            self._redis_connected = True
            logger.info("Connected to Redis at %s for circuit breaker state.", self.redis_url)
            return self._redis
        except Exception as exc:
            self._redis_connected = False
            self._redis = None
            logger.debug("Redis unavailable (%s); using in-memory circuit breaker fallback.", exc)
            return None

    async def is_redis_connected(self) -> bool:
        redis_client = await self._get_redis()
        if not redis_client:
            return False
        try:
            await redis_client.ping()
            return True
        except Exception:
            self._redis_connected = False
            self._redis = None
            return False

    async def get_state(self, lab: Lab) -> CircuitState:
        lab_key = lab.value
        redis_client = await self._get_redis()

        if redis_client:
            try:
                state_str = await redis_client.get(f"veritas:cb:{lab_key}:state") or CircuitState.CLOSED.value
                last_fail_str = await redis_client.get(f"veritas:cb:{lab_key}:last_fail") or "0"
                last_fail = float(last_fail_str)

                if state_str == CircuitState.OPEN.value:
                    if time.time() - last_fail > self.cooldown_seconds:
                        await redis_client.set(f"veritas:cb:{lab_key}:state", CircuitState.HALF_OPEN.value)
                        return CircuitState.HALF_OPEN
                    return CircuitState.OPEN
                if state_str == CircuitState.HALF_OPEN.value:
                    return CircuitState.HALF_OPEN
                return CircuitState.CLOSED
            except Exception:
                pass

        # In-memory fallback
        info = self._local_states.setdefault(lab_key, {
            "state": CircuitState.CLOSED.value,
            "failure_count": 0,
            "last_failure_time": 0.0,
        })
        current_state = info["state"]
        if current_state == CircuitState.OPEN.value:
            if time.time() - info["last_failure_time"] > self.cooldown_seconds:
                info["state"] = CircuitState.HALF_OPEN.value
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN
        if current_state == CircuitState.HALF_OPEN.value:
            return CircuitState.HALF_OPEN
        return CircuitState.CLOSED

    async def can_execute(self, lab: Lab) -> bool:
        state = await self.get_state(lab)
        return state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    async def record_success(self, lab: Lab) -> None:
        lab_key = lab.value
        redis_client = await self._get_redis()

        if redis_client:
            try:
                await redis_client.set(f"veritas:cb:{lab_key}:state", CircuitState.CLOSED.value)
                await redis_client.set(f"veritas:cb:{lab_key}:failures", "0")
                return
            except Exception:
                pass

        info = self._local_states.setdefault(lab_key, {})
        info["state"] = CircuitState.CLOSED.value
        info["failure_count"] = 0

    async def record_failure(self, lab: Lab) -> None:
        lab_key = lab.value
        now = time.time()
        redis_client = await self._get_redis()

        if redis_client:
            try:
                failures = await redis_client.incr(f"veritas:cb:{lab_key}:failures")
                await redis_client.set(f"veritas:cb:{lab_key}:last_fail", str(now))
                if failures >= self.failure_threshold:
                    await redis_client.set(f"veritas:cb:{lab_key}:state", CircuitState.OPEN.value)
                    logger.warning("Circuit breaker tripped to OPEN for %s (%d failures)", lab_key, failures)
                return
            except Exception:
                pass

        info = self._local_states.setdefault(lab_key, {
            "state": CircuitState.CLOSED.value,
            "failure_count": 0,
            "last_failure_time": 0.0,
        })
        info["failure_count"] += 1
        info["last_failure_time"] = now
        if info["failure_count"] >= self.failure_threshold:
            info["state"] = CircuitState.OPEN.value
            logger.warning("In-memory circuit breaker tripped to OPEN for %s (%d failures)", lab_key, info["failure_count"])

    async def trip_immediately(self, lab: Lab) -> None:
        """Immediately trips the circuit breaker to OPEN on fatal quota/auth errors."""
        lab_key = lab.value
        now = time.time()
        redis_client = await self._get_redis()

        if redis_client:
            try:
                await redis_client.set(f"veritas:cb:{lab_key}:failures", str(self.failure_threshold))
                await redis_client.set(f"veritas:cb:{lab_key}:last_fail", str(now))
                await redis_client.set(f"veritas:cb:{lab_key}:state", CircuitState.OPEN.value)
                logger.warning("Circuit breaker immediately tripped to OPEN for %s (fatal quota/auth error)", lab_key)
                return
            except Exception:
                pass

        info = self._local_states.setdefault(lab_key, {
            "state": CircuitState.CLOSED.value,
            "failure_count": 0,
            "last_failure_time": 0.0,
        })
        info["failure_count"] = self.failure_threshold
        info["last_failure_time"] = now
        info["state"] = CircuitState.OPEN.value
        logger.warning("In-memory circuit breaker immediately tripped to OPEN for %s (fatal quota/auth error)", lab_key)

    async def reset(self, lab: Lab) -> None:
        lab_key = lab.value
        redis_client = await self._get_redis()

        if redis_client:
            try:
                await redis_client.set(f"veritas:cb:{lab_key}:state", CircuitState.CLOSED.value)
                await redis_client.set(f"veritas:cb:{lab_key}:failures", "0")
                await redis_client.set(f"veritas:cb:{lab_key}:last_fail", "0")
                logger.info("Reset circuit for %s via Redis", lab_key)
                return
            except Exception:
                pass

        info = self._local_states.setdefault(lab_key, {})
        info["state"] = CircuitState.CLOSED.value
        info["failure_count"] = 0
        info["last_failure_time"] = 0.0
        logger.info("Reset circuit for %s via in-memory store", lab_key)

    async def get_all_status(self) -> dict[str, Any]:
        redis_ok = await self.is_redis_connected()
        providers_status: dict[str, Any] = {}

        for lab in [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI, Lab.OLLAMA]:
            state = await self.get_state(lab)
            lab_key = lab.value
            fail_count = 0

            cooldown_rem = 0.0
            redis_client = await self._get_redis()
            if redis_client and redis_ok:
                try:
                    fail_str = await redis_client.get(f"veritas:cb:{lab_key}:failures") or "0"
                    fail_count = int(fail_str)
                    last_fail_str = await redis_client.get(f"veritas:cb:{lab_key}:last_failure")
                    if last_fail_str and state == CircuitState.OPEN:
                        elapsed = time.time() - float(last_fail_str)
                        cooldown_rem = max(0.0, self.cooldown_seconds - elapsed)
                except Exception:
                    pass
            else:
                local_info = self._local_states.get(lab_key, {})
                fail_count = local_info.get("failure_count", 0)
                if state == CircuitState.OPEN:
                    elapsed = time.time() - local_info.get("last_failure_time", 0.0)
                    cooldown_rem = max(0.0, self.cooldown_seconds - elapsed)

            providers_status[lab_key] = {
                "lab": lab_key,
                "state": state.value,
                "failure_count": fail_count,
                "cooldown_seconds": self.cooldown_seconds,
                "cooldown_remaining": round(cooldown_rem, 1),
            }

        active_count = sum(1 for p in providers_status.values() if p["state"] != CircuitState.OPEN.value)
        return {
            "total_configured": len(providers_status),
            "active_count": active_count,
            "redis_connected": redis_ok,
            "providers": providers_status,
        }


# Global singleton instance
_circuit_breaker: CircuitBreakerManager | None = None


def get_circuit_breaker() -> CircuitBreakerManager:
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreakerManager()
    return _circuit_breaker


ProviderCircuitBreaker = CircuitBreakerManager

