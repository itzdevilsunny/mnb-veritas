from __future__ import annotations

import logging
from app.gateway.base import LLMProvider
from app.gateway.circuit_breaker import CircuitBreakerManager, get_circuit_breaker
from app.gateway.moe_router import MoERoute, MoERouter, MoETelemetry
from app.models.schemas import Lab

logger = logging.getLogger("veritas.router")


class VeritasRouter:
    """
    Layer 1: Multi-Lab MoE Router with strict Cross-Lab Independence,
    Redis Circuit Breaker integration, and Zero-PII Telemetry.
    Zero mock fallbacks in production paths.
    """

    CROSS_LAB_ORDER: dict[Lab, list[Lab]] = {
        Lab.ANTHROPIC: [Lab.OPENAI, Lab.GOOGLE, Lab.XAI, Lab.OLLAMA],
        Lab.OPENAI: [Lab.GOOGLE, Lab.ANTHROPIC, Lab.XAI, Lab.OLLAMA],
        Lab.GOOGLE: [Lab.OPENAI, Lab.ANTHROPIC, Lab.XAI, Lab.OLLAMA],
        Lab.XAI: [Lab.GOOGLE, Lab.OPENAI, Lab.ANTHROPIC, Lab.OLLAMA],
        Lab.OLLAMA: [Lab.GOOGLE, Lab.OPENAI, Lab.ANTHROPIC, Lab.XAI],
        Lab.AUTO: [Lab.GOOGLE, Lab.OPENAI, Lab.ANTHROPIC, Lab.XAI, Lab.OLLAMA],
    }

    def __init__(
        self,
        providers: dict[Lab, LLMProvider],
        circuit_breaker: CircuitBreakerManager | None = None,
    ) -> None:
        self.providers = providers
        self.circuit_breaker = circuit_breaker or get_circuit_breaker()
        self.moe = MoERouter(providers=self.providers, circuit_breaker=self.circuit_breaker)
        self.last_failover_occurred: bool = False
        self.last_telemetry: MoETelemetry | None = None

    @property
    def last_failure_reason(self) -> str | None:
        return getattr(self.moe, "last_failure_reason", None)

    @last_failure_reason.setter
    def last_failure_reason(self, val: str | None) -> None:
        if hasattr(self.moe, "last_failure_reason"):
            self.moe.last_failure_reason = val

    async def call_with_failover(
        self,
        preferred_labs: list[Lab],
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        excluded_labs: set[Lab] | None = None,
        route: MoERoute | None = None,
        query: str = "",
    ) -> tuple[str, LLMProvider, bool]:
        """
        Executes generation through the MoE provider chain using real live providers.
        Automatically skips OPEN circuits in 0ms, fails over rapidly, and records zero-PII telemetry.
        Strict cross-lab independence is enforced via excluded_labs.
        Returns: (response_text, provider_used, failover_triggered)
        """
        # Determine MoE route if not explicitly provided
        selected_route = route or self.moe.classify_task(
            query=query or user_prompt,
            is_audit=("audit" in system_prompt.lower() or "compliance" in system_prompt.lower()),
        )

        content, provider, telemetry = await self.moe.execute_route(
            candidate_labs=preferred_labs,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            route=selected_route,
            temperature=temperature,
            excluded_labs=excluded_labs,
            query_context=query,
        )
        self.last_failover_occurred = telemetry.failover_triggered
        self.last_telemetry = telemetry
        return content, provider, telemetry.failover_triggered

    def get_auditor_chain(self, generator_lab: Lab) -> list[Lab]:
        """
        Rule: Cross-Lab Independence. A generator model CANNOT audit its own draft.
        """
        candidates = self.CROSS_LAB_ORDER.get(
            generator_lab, [Lab.OPENAI, Lab.GOOGLE, Lab.ANTHROPIC, Lab.XAI, Lab.OLLAMA]
        )
        return [lab for lab in candidates if lab != generator_lab and lab in self.providers]

    async def call_cross_lab_concurrent(
        self,
        candidate_labs: list[Lab],
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        excluded_labs: set[Lab] | None = None,
    ) -> tuple[str, LLMProvider, MoETelemetry]:
        """
        Queries candidate secondary auditor labs concurrently via asyncio.gather.
        Skips OPEN circuits in 0ms, fires healthy distinct labs simultaneously,
        and returns the first valid entailment verification result.
        """
        content, provider, telemetry = await self.moe.execute_concurrent_audit(
            candidate_labs=candidate_labs,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            excluded_labs=excluded_labs,
        )
        self.last_failover_occurred = telemetry.failover_triggered
        self.last_telemetry = telemetry
        return content, provider, telemetry


MultiLabGateway = VeritasRouter


