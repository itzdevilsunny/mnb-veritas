from __future__ import annotations

import asyncio
import logging
import re
import time
from enum import Enum
from typing import Any
from app.core.config import get_settings
from app.gateway.base import LLMProvider
from app.gateway.circuit_breaker import CircuitBreakerManager, CircuitState, get_circuit_breaker
from app.models.schemas import Lab

logger = logging.getLogger("veritas.moe_router")


class MoERoute(str, Enum):
    FAST_EXTRACTION = "fast_extraction"
    DEEP_AUDIT = "deep_audit"
    DETERMINISTIC_VETO = "deterministic_veto"


class MoETelemetry:
    """
    Zero-PII Telemetry metadata capturing execution statistics.
    Never stores or logs raw queries, prompts, documents, or answers.
    """

    def __init__(
        self,
        lab: str,
        model: str,
        moe_route: MoERoute,
        escalated: bool,
        latency_ms: int,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost_usd: float,
        failover_triggered: bool,
        circuit_state: str,
    ) -> None:
        self.lab = lab
        self.model = model
        self.moe_route = moe_route
        self.escalated = escalated
        self.latency_ms = latency_ms
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.estimated_cost_usd = estimated_cost_usd
        self.failover_triggered = failover_triggered
        self.circuit_state = circuit_state

    def to_dict(self) -> dict[str, Any]:
        return {
            "lab": self.lab,
            "model": self.model,
            "moe_route": self.moe_route.value,
            "escalated": self.escalated,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "failover_triggered": self.failover_triggered,
            "circuit_state": self.circuit_state,
        }


# Model Cost Estimates per 1,000,000 tokens (USD)
TOKEN_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_m, output_per_m)
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "gemini-3.5-flash": (0.10, 0.40),
    "gemini-3.5-flash-lite": (0.05, 0.20),
    "gemma-4-26b-a4b-it": (0.07, 0.28),
    "grok-2": (2.00, 10.00),
}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculates zero-PII cost estimation in USD based on published tier pricing."""
    for prefix, (in_price, out_price) in TOKEN_PRICING.items():
        if prefix in model.lower():
            cost = (prompt_tokens / 1_000_000.0 * in_price) + (completion_tokens / 1_000_000.0 * out_price)
            return round(cost, 6)
    # Default fallback rate: $1.00 / $4.00
    return round((prompt_tokens / 1_000_000.0 * 1.0) + (completion_tokens / 1_000_000.0 * 4.0), 6)


class MoERouter:
    """
    Task-Based Mixture of Experts (MoE) Gateway Router.
    Routes real live LLM calls based on task requirements, query complexity,
    and instantaneous circuit breaker health (0ms skipping of OPEN circuits).
    """

    def __init__(
        self,
        providers: dict[Lab, LLMProvider],
        circuit_breaker: CircuitBreakerManager | None = None,
    ) -> None:
        self.providers = providers
        self.circuit_breaker = circuit_breaker or get_circuit_breaker()
        self.settings = get_settings()

    def classify_task(
        self,
        query: str,
        is_audit: bool = False,
        is_critical: bool = False,
    ) -> MoERoute:
        """
        Classifies incoming prompt to select the optimal expert tier:
        - DEEP_AUDIT: for cross-lab audit checks or high-stakes statutory / multi-number claims.
        - FAST_EXTRACTION: for straightforward claim extraction and single-fact synthesis.
        """
        if is_audit or is_critical:
            return MoERoute.DEEP_AUDIT

        q_lower = query.lower()
        critical_words = {"statutory", "mandate", "cushion", "sovereign", "penalty", "contingent"}
        if any(w in q_lower for w in critical_words):
            return MoERoute.DEEP_AUDIT

        # Multiple numerical tokens in query indicate multi-number comparative reasoning
        numeric_count = len(re.findall(r"\d+", query))
        if numeric_count >= 3:
            return MoERoute.DEEP_AUDIT

        return MoERoute.FAST_EXTRACTION

    def resolve_model_for_route(self, lab: Lab, route: MoERoute) -> str:
        """Resolves the configured live model ID based on the expert tier route."""
        s = self.settings
        if route == MoERoute.DEEP_AUDIT:
            if lab == Lab.ANTHROPIC:
                return s.AUDITOR_ANTHROPIC_MODEL
            elif lab == Lab.OPENAI:
                return s.AUDITOR_OPENAI_MODEL
            elif lab == Lab.GOOGLE:
                return s.AUDITOR_GEMINI_MODEL
            elif lab == Lab.XAI:
                return s.AUDITOR_XAI_MODEL
            elif lab == Lab.OLLAMA:
                return getattr(s, "AUDITOR_OLLAMA_MODEL", "llama3.2:latest")
        else:
            if lab == Lab.ANTHROPIC:
                return s.FAST_ANTHROPIC_MODEL
            elif lab == Lab.OPENAI:
                return s.FAST_OPENAI_MODEL
            elif lab == Lab.GOOGLE:
                return s.FAST_GEMINI_MODEL
            elif lab == Lab.XAI:
                return s.FAST_XAI_MODEL
            elif lab == Lab.OLLAMA:
                return getattr(s, "FAST_OLLAMA_MODEL", "llama3.2:latest")

        if lab == Lab.OLLAMA:
            return getattr(s, "OLLAMA_MODEL", "llama3.2:latest")
        return s.DEFAULT_GEMINI_MODEL if lab == Lab.GOOGLE else getattr(s, f"{lab.name}_MODEL", "default")

    async def execute_route(
        self,
        candidate_labs: list[Lab],
        system_prompt: str,
        user_prompt: str,
        route: MoERoute = MoERoute.FAST_EXTRACTION,
        temperature: float = 0.0,
        excluded_labs: set[Lab] | None = None,
        query_context: str = "",
    ) -> tuple[str, LLMProvider, MoETelemetry]:
        """
        Executes generation using live real provider adapters.
        Skips OPEN circuits in 0ms, fails over rapidly, and returns Zero-PII Telemetry.
        """
        excluded = excluded_labs or set()
        attempts = 0
        last_exc: Exception | None = None

        # Build clean candidate list
        clean_chain: list[Lab] = []
        for lab in candidate_labs:
            if lab in excluded:
                continue
            if lab == Lab.AUTO:
                for default_lab in [Lab.GOOGLE, Lab.OPENAI, Lab.ANTHROPIC, Lab.XAI]:
                    if default_lab not in clean_chain and default_lab not in excluded:
                        clean_chain.append(default_lab)
            elif lab not in clean_chain:
                clean_chain.append(lab)

        for lab in clean_chain:
            provider = self.providers.get(lab)
            if not provider:
                continue

            # 0ms Circuit Breaker check
            circuit_open = not (await self.circuit_breaker.can_execute(lab))
            if circuit_open:
                logger.info("Circuit breaker OPEN for %s. Skipping in 0ms.", lab.value)
                continue

            # Dynamically set expert model for this call
            target_model = self.resolve_model_for_route(lab, route)
            provider.model = target_model

            attempts += 1
            t0 = time.perf_counter()
            try:
                content = await provider.generate(system_prompt, user_prompt, temperature=temperature)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)

                # Record healthy execution
                await self.circuit_breaker.record_success(lab)

                # Extract token counts
                usage = getattr(provider, "last_usage", {})
                p_toks = usage.get("prompt_tokens", len(user_prompt) // 4)
                c_toks = usage.get("completion_tokens", len(content) // 4)
                cost = calculate_cost(target_model, p_toks, c_toks)

                cb_state = (await self.circuit_breaker.get_state(lab)).value
                telemetry = MoETelemetry(
                    lab=lab.value,
                    model=target_model,
                    moe_route=route,
                    escalated=(route == MoERoute.DEEP_AUDIT),
                    latency_ms=elapsed_ms,
                    prompt_tokens=p_toks,
                    completion_tokens=c_toks,
                    estimated_cost_usd=cost,
                    failover_triggered=(attempts > 1),
                    circuit_state=cb_state,
                )

                logger.info(
                    "Zero-PII Telemetry: provider=%s model=%s route=%s latency=%dms cost=$%f failover=%s",
                    lab.value,
                    target_model,
                    route.value,
                    elapsed_ms,
                    cost,
                    (attempts > 1),
                )
                return content, provider, telemetry

            except Exception as exc:
                err_str = str(exc).lower()
                is_fatal = any(
                    k in err_str
                    for k in [
                        "400", "401", "402", "403", "429", "quota", "credit",
                        "unauthorized", "forbidden", "invalid_api_key", "billing", "balance",
                        "connection refused", "connecterror", "all connection attempts failed",
                    ]
                )
                if is_fatal:
                    await self.circuit_breaker.trip_immediately(lab)
                else:
                    await self.circuit_breaker.record_failure(lab)

                logger.warning(
                    "Zero-PII Telemetry: Provider %s failed (fatal=%s). Initiating failover...",
                    lab.value,
                    is_fatal,
                )
                last_exc = exc
                continue

        # If all candidates exhausted, try ANY registered provider not in clean_chain or excluded
        for lab, provider in self.providers.items():
            if lab in clean_chain or lab in excluded:
                continue
            if not (await self.circuit_breaker.can_execute(lab)):
                continue

            target_model = self.resolve_model_for_route(lab, route)
            provider.model = target_model
            attempts += 1
            t0 = time.perf_counter()
            try:
                content = await provider.generate(system_prompt, user_prompt, temperature=temperature)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                await self.circuit_breaker.record_success(lab)

                usage = getattr(provider, "last_usage", {})
                p_toks = usage.get("prompt_tokens", len(user_prompt) // 4)
                c_toks = usage.get("completion_tokens", len(content) // 4)
                cost = calculate_cost(target_model, p_toks, c_toks)
                cb_state = (await self.circuit_breaker.get_state(lab)).value

                telemetry = MoETelemetry(
                    lab=lab.value,
                    model=target_model,
                    moe_route=route,
                    escalated=(route == MoERoute.DEEP_AUDIT),
                    latency_ms=elapsed_ms,
                    prompt_tokens=p_toks,
                    completion_tokens=c_toks,
                    estimated_cost_usd=cost,
                    failover_triggered=True,
                    circuit_state=cb_state,
                )
                return content, provider, telemetry
            except Exception as exc:
                await self.circuit_breaker.record_failure(lab)
                last_exc = exc
                continue

        # Strictly Zero Mock rule: raise error if no real provider could fulfill the request
        raise RuntimeError(
            f"No live LLM provider available to fulfill request across configured labs {list(self.providers.keys())}. "
            f"All circuits exhausted or excluded. Last error: {last_exc}"
        )

    async def execute_concurrent_audit(
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
        excluded = excluded_labs or set()
        clean_chain: list[Lab] = []
        for lab in candidate_labs:
            if lab in excluded or lab == Lab.AUTO:
                continue
            if lab not in clean_chain:
                clean_chain.append(lab)

        # 0ms Circuit Breaker pre-filter: gather healthy registered labs
        healthy_candidates: list[Lab] = []
        for lab in clean_chain:
            if lab in self.providers and await self.circuit_breaker.can_execute(lab):
                healthy_candidates.append(lab)
            else:
                logger.info("Circuit breaker OPEN for %s. Skipping in 0ms.", lab.value)

        if not healthy_candidates:
            raise RuntimeError(
                f"No healthy secondary auditor available across candidate labs {clean_chain}. "
                "All circuits OPEN, exhausted, or excluded."
            )

        async def _query_single_auditor(lab: Lab) -> tuple[str, LLMProvider, MoETelemetry]:
            provider = self.providers[lab]
            target_model = self.resolve_model_for_route(lab, MoERoute.DEEP_AUDIT)
            provider.model = target_model
            t0 = time.perf_counter()
            try:
                content = await provider.generate(system_prompt, user_prompt, temperature=temperature)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                await self.circuit_breaker.record_success(lab)

                usage = getattr(provider, "last_usage", {})
                p_toks = usage.get("prompt_tokens", len(user_prompt) // 4)
                c_toks = usage.get("completion_tokens", len(content) // 4)
                cost = calculate_cost(target_model, p_toks, c_toks)
                cb_state = (await self.circuit_breaker.get_state(lab)).value

                telemetry = MoETelemetry(
                    lab=lab.value,
                    model=target_model,
                    moe_route=MoERoute.DEEP_AUDIT,
                    escalated=True,
                    latency_ms=elapsed_ms,
                    prompt_tokens=p_toks,
                    completion_tokens=c_toks,
                    estimated_cost_usd=cost,
                    failover_triggered=False,
                    circuit_state=cb_state,
                )
                logger.info(
                    "Zero-PII Telemetry: concurrent auditor=%s model=%s latency=%dms cost=$%f",
                    lab.value,
                    target_model,
                    elapsed_ms,
                    cost,
                )
                return content, provider, telemetry
            except Exception as exc:
                err_str = str(exc).lower()
                is_fatal = any(
                    k in err_str
                    for k in [
                        "400", "401", "402", "403", "429", "quota", "credit",
                        "unauthorized", "forbidden", "invalid_api_key", "billing", "balance",
                        "connection refused", "connecterror", "all connection attempts failed",
                    ]
                )
                if is_fatal:
                    await self.circuit_breaker.trip_immediately(lab)
                else:
                    await self.circuit_breaker.record_failure(lab)
                logger.warning(
                    "Zero-PII Telemetry: Concurrent auditor %s failed (fatal=%s): %s",
                    lab.value,
                    is_fatal,
                    exc,
                )
                raise exc

        tasks = [asyncio.create_task(_query_single_auditor(lab)) for lab in healthy_candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        last_err: Exception | None = None
        for res in results:
            if not isinstance(res, Exception):
                return res
            last_err = res

        raise last_err or RuntimeError(
            f"All concurrent secondary auditor calls failed across {healthy_candidates}."
        )

