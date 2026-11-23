from __future__ import annotations

import logging
import time
from app.gateway.base import LLMProvider
from app.gateway.circuit_breaker import CircuitBreakerManager, get_circuit_breaker
from app.models.schemas import Lab

logger = logging.getLogger("veritas.router")


class VeritasRouter:
    """
    Layer 1: Multi-Lab Router with strict Cross-Lab Independence,
    Redis Circuit Breaker integration, and Zero-PII Telemetry.
    """

    CROSS_LAB_ORDER: dict[Lab, list[Lab]] = {
        Lab.ANTHROPIC: [Lab.OPENAI, Lab.GOOGLE, Lab.XAI],
        Lab.OPENAI: [Lab.ANTHROPIC, Lab.GOOGLE, Lab.XAI],
        Lab.GOOGLE: [Lab.ANTHROPIC, Lab.OPENAI, Lab.XAI],
        Lab.XAI: [Lab.ANTHROPIC, Lab.GOOGLE, Lab.OPENAI],
        Lab.AUTO: [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI],
    }

    def __init__(
        self,
        providers: dict[Lab, LLMProvider],
        circuit_breaker: CircuitBreakerManager | None = None,
    ) -> None:
        self.providers = providers
        self.circuit_breaker = circuit_breaker or get_circuit_breaker()

    async def call_with_failover(
        self,
        preferred_labs: list[Lab],
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> tuple[str, LLMProvider, bool]:
        """
        Executes generation through the provider chain, automatically failing over on error
        or when a provider circuit is OPEN.
        Returns: (response_text, provider_used, failover_triggered)
        """
        last_exc: Exception | None = None
        attempts = 0

        # Expand AUTO to default chain if requested
        chain: list[Lab] = []
        for lab in preferred_labs:
            if lab == Lab.AUTO:
                for default_lab in [Lab.ANTHROPIC, Lab.OPENAI, Lab.GOOGLE, Lab.XAI]:
                    if default_lab not in chain:
                        chain.append(default_lab)
            elif lab not in chain:
                chain.append(lab)

        for lab in chain:
            provider = self.providers.get(lab)
            if not provider:
                continue

            # Check circuit breaker state
            can_run = await self.circuit_breaker.can_execute(lab)
            if not can_run:
                logger.warning("Circuit breaker OPEN for %s. Skipping in failover chain.", lab.value)
                continue

            attempts += 1
            try:
                t0 = time.perf_counter()
                content = await provider.generate(system_prompt, user_prompt, temperature=temperature)
                dt_ms = int((time.perf_counter() - t0) * 1000)

                # Record healthy execution in circuit breaker
                await self.circuit_breaker.record_success(lab)

                # Zero-PII Telemetry log: only metadata, latency, and model id
                logger.info(
                    "Zero-PII Telemetry: provider=%s model=%s latency_ms=%d failover=%s",
                    provider.lab.value,
                    provider.model,
                    dt_ms,
                    (attempts > 1),
                )
                return content, provider, (attempts > 1)
            except Exception as exc:
                await self.circuit_breaker.record_failure(lab)
                logger.warning("Provider %s failed: %s. Initiating failover...", lab.value, exc)
                last_exc = exc
                continue

        # If all preferred failed, try ANY available provider in registry
        for lab, provider in self.providers.items():
            if lab in chain:
                continue
            can_run = await self.circuit_breaker.can_execute(lab)
            if not can_run:
                continue
            try:
                content = await provider.generate(system_prompt, user_prompt, temperature=temperature)
                await self.circuit_breaker.record_success(lab)
                return content, provider, True
            except Exception as exc:
                await self.circuit_breaker.record_failure(lab)
                continue

        # Ultimate fallback: local deterministic MockProvider
        from app.gateway.adapters import MockProvider
        fallback_mock = MockProvider(Lab.ANTHROPIC, "claude-3-5-sonnet-fallback")
        content = await fallback_mock.generate(system_prompt, user_prompt, temperature=temperature)
        logger.info("Fell back to internal deterministic engine after provider exhaustion.")
        return content, fallback_mock, True

    def get_auditor_chain(self, generator_lab: Lab) -> list[Lab]:
        """
        Rule: Cross-Lab Independence. A generator model CANNOT audit its own draft.
        """
        candidates = self.CROSS_LAB_ORDER.get(
            generator_lab, [Lab.OPENAI, Lab.GOOGLE, Lab.ANTHROPIC, Lab.XAI]
        )
        return [lab for lab in candidates if lab != generator_lab and lab in self.providers]


MultiLabGateway = VeritasRouter

