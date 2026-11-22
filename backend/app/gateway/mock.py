from __future__ import annotations

from typing import Callable
from app.gateway.adapters import MockProvider
from app.gateway.base import BaseLLMAdapter, GenerationResult, ZeroPIITelemetry
from app.models.schemas import Lab


class MockAdapter(MockProvider):
    """
    Offline adapter compatible with both MockProvider and BaseLLMAdapter contracts.
    """

    def __init__(
        self,
        lab: Lab,
        model: str,
        response: str | Callable[[str, str], str] = "{}",
        fail_times: int = 0,
    ) -> None:
        canned = response if isinstance(response, str) else None
        super().__init__(lab, model, canned_response=canned)
        self._custom_response = response
        self.fail_times = fail_times
        self.calls = 0
        self.last_user_prompt: str | None = None

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        self.calls += 1
        self.last_user_prompt = user_prompt
        if self.calls <= self.fail_times:
            raise TimeoutError(f"simulated timeout for {self.lab.value}")
        if callable(self._custom_response):
            return self._custom_response(system_prompt, user_prompt)
        return await super().generate(system_prompt, user_prompt, temperature)

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        content = await self.generate(system_prompt, user_prompt, temperature)
        return GenerationResult(
            content=content,
            telemetry=ZeroPIITelemetry(
                lab=self.lab,
                model=self.model,
                latency_ms=7,
                prompt_tokens=100,
                completion_tokens=40,
                estimated_cost_usd=0.0001,
            ),
        )
