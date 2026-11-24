from __future__ import annotations

import logging
from app.core.config import get_settings
from app.gateway.adapters import (
    AnthropicProvider,
    GeminiProvider,
    OpenAICompatProvider,
)
from app.gateway.base import LLMProvider
from app.gateway.circuit_breaker import get_circuit_breaker
from app.gateway.router import VeritasRouter
from app.models.schemas import Lab

logger = logging.getLogger("veritas.gateway.registry")

_default_router: VeritasRouter | None = None


def build_default_router(force_refresh: bool = False) -> VeritasRouter:
    """
    Constructs or returns the cached Veritas multi-lab router using real live providers
    backed by environment keys (.env). Strictly zero mock fallbacks in production.
    """
    global _default_router
    if _default_router is not None and not force_refresh:
        return _default_router

    settings = get_settings()
    providers: dict[Lab, LLMProvider] = {}

    # Anthropic
    if settings.ANTHROPIC_API_KEY:
        providers[Lab.ANTHROPIC] = AnthropicProvider(
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
        )

    # OpenAI
    if settings.OPENAI_API_KEY:
        providers[Lab.OPENAI] = OpenAICompatProvider(
            lab=Lab.OPENAI,
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            fallback_models=["gpt-4o-mini", "gpt-4o"],
        )

    # Google Gemini
    if settings.GEMINI_API_KEY:
        providers[Lab.GOOGLE] = GeminiProvider(
            model=settings.GEMINI_MODEL,
            api_key=settings.GEMINI_API_KEY,
        )

    # xAI Grok
    if settings.XAI_API_KEY:
        providers[Lab.XAI] = OpenAICompatProvider(
            lab=Lab.XAI,
            model=settings.XAI_MODEL,
            api_key=settings.XAI_API_KEY,
            base_url="https://api.x.ai/v1",
            fallback_models=["grok-2", "grok-2-latest", "grok-beta"],
        )

    logger.info("VeritasRouter initialized with %d live providers: %s", len(providers), list(providers.keys()))
    _default_router = VeritasRouter(providers, circuit_breaker=get_circuit_breaker())
    return _default_router

