from __future__ import annotations

from app.core.config import get_settings
from app.gateway.adapters import (
    AnthropicProvider,
    GeminiProvider,
    MockProvider,
    OpenAICompatProvider,
)
from app.gateway.base import LLMProvider
from app.gateway.circuit_breaker import get_circuit_breaker
from app.gateway.router import VeritasRouter
from app.models.schemas import Lab


def build_default_router() -> VeritasRouter:
    """
    Constructs the Veritas multi-lab router using environment keys if present,
    falling back to MockProvider for zero-dependency local runs or tests.
    """
    settings = get_settings()
    providers: dict[Lab, LLMProvider] = {}

    # Anthropic
    if settings.ANTHROPIC_API_KEY:
        providers[Lab.ANTHROPIC] = AnthropicProvider(
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
        )
    else:
        providers[Lab.ANTHROPIC] = MockProvider(Lab.ANTHROPIC, "claude-3-5-sonnet-20241022")

    # OpenAI
    if settings.OPENAI_API_KEY:
        providers[Lab.OPENAI] = OpenAICompatProvider(
            lab=Lab.OPENAI,
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            fallback_models=["gpt-4o-mini", "gpt-4o"],
        )
    else:
        providers[Lab.OPENAI] = MockProvider(Lab.OPENAI, "gpt-4o-mini")

    # Google Gemini
    if settings.GEMINI_API_KEY:
        providers[Lab.GOOGLE] = GeminiProvider(
            model=settings.GEMINI_MODEL,
            api_key=settings.GEMINI_API_KEY,
        )
    else:
        providers[Lab.GOOGLE] = MockProvider(Lab.GOOGLE, "gemini-1.5-flash")

    # xAI Grok
    if settings.XAI_API_KEY:
        providers[Lab.XAI] = OpenAICompatProvider(
            lab=Lab.XAI,
            model=settings.XAI_MODEL,
            api_key=settings.XAI_API_KEY,
            base_url="https://api.x.ai/v1",
            fallback_models=["grok-2", "grok-2-latest", "grok-beta"],
        )
    else:
        providers[Lab.XAI] = MockProvider(Lab.XAI, "grok-2")

    return VeritasRouter(providers, circuit_breaker=get_circuit_breaker())
