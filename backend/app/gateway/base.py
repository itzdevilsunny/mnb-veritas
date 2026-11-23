from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from app.models.schemas import Lab


class GatewayUnavailable(RuntimeError):
    """Every provider in the requested chain failed or has an open circuit."""


@dataclass
class ZeroPIITelemetry:
    """Metadata only. Never holds prompts, completions or source text."""
    lab: Lab
    model: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    failover_triggered: bool = False
    failed_attempts: list[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    content: str
    telemetry: ZeroPIITelemetry


# USD per 1M tokens (input, output)
PRICING_PER_1M: dict[str, tuple[float, float]] = {
    # Production Real-world Models
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-sonnet-latest": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "grok-2": (2.00, 10.00),
    # Fallback & Compatibility Aliases
    "claude-sonnet-5-5": (3.00, 15.00),
    "claude-opus-5-5": (15.00, 75.00),
    "claude-haiku-5-5": (0.80, 4.00),
    "gpt-6.1-terra": (2.50, 10.00),
    "gpt-6.1-sol": (1.25, 5.00),
    "gemini-4-hydrogen": (0.35, 1.40),
    "gemini-4-carbon": (2.00, 8.00),
    "grok-4.3": (3.00, 15.00),
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_rate, out_rate = PRICING_PER_1M.get(model, (2.00, 8.00))
    return round((prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000, 6)


class LLMProvider(ABC):
    lab: Lab
    model: str

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        """Generates response text from the underlying provider."""
        ...

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generates response with Zero-PII telemetry metadata."""
        content = await self.generate(system_prompt, user_prompt, temperature)
        return GenerationResult(
            content=content,
            telemetry=ZeroPIITelemetry(
                lab=self.lab,
                model=self.model,
                latency_ms=10,
                prompt_tokens=len(user_prompt) // 4,
                completion_tokens=len(content) // 4,
                estimated_cost_usd=estimate_cost_usd(self.model, len(user_prompt) // 4, len(content) // 4),
            ),
        )


BaseLLMAdapter = LLMProvider
