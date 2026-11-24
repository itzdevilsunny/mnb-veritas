from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from app.gateway.base import LLMProvider
from app.gateway.http_pool import get_shared_http_client
from app.models.schemas import Lab

logger = logging.getLogger("veritas.gateway.adapters")

FATAL_ERROR_KEYWORDS = {
    "credit_balance_exhausted",
    "insufficient_quota",
    "credit",
    "balance",
    "unauthorized",
    "invalid_api_key",
    "authentication",
    "billing",
    "account_deactivated",
    "401",
    "402",
    "403",
    "connection refused",
    "connecterror",
    "all connection attempts failed",
}


def is_fatal_auth_or_quota_error(exc: Exception) -> bool:
    """Returns True if the exception represents an unrecoverable auth, quota, or billing failure."""
    err_str = str(exc).lower()
    return any(k in err_str for k in FATAL_ERROR_KEYWORDS)


class AnthropicProvider(LLMProvider):
    lab = Lab.ANTHROPIC

    def __init__(self, model: str = "claude-3-5-sonnet-20241022", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.last_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        client = get_shared_http_client()
        models_to_try = [self.model, "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
        last_err: Exception | None = None

        for m in models_to_try:
            try:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": m,
                        "max_tokens": 2048,
                        "temperature": temperature,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )
                if resp.status_code == 404 or "not_found" in resp.text.lower():
                    continue
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                self.last_usage = {
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                }
                blocks = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
                self.model = m
                return "\n".join(blocks).strip()
            except Exception as exc:
                last_err = exc
                if is_fatal_auth_or_quota_error(exc):
                    raise exc
                err_lower = str(exc).lower()
                if "404" in err_lower or "not_found" in err_lower:
                    continue
                raise exc

        raise last_err or RuntimeError(f"Anthropic model generation failed for {self.model}")


class OpenAICompatProvider(LLMProvider):
    """Async provider for OpenAI, xAI Grok, or custom OpenAI-compatible endpoints."""

    def __init__(
        self,
        lab: Lab,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        fallback_models: list[str] | None = None,
    ) -> None:
        self.lab = lab
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.fallback_models = fallback_models or []
        self.last_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError(f"API key missing for provider {self.lab.value}")
        from openai import AsyncOpenAI

        # Use pooled httpx AsyncClient for connection reuse and tightened timeouts
        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=get_shared_http_client(),
            max_retries=0,
        )
        models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
        last_err: Exception | None = None

        for m in models_to_try:
            try:
                resp = await client.chat.completions.create(
                    model=m,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                self.model = m
                if resp.usage:
                    self.last_usage = {
                        "prompt_tokens": resp.usage.prompt_tokens or 0,
                        "completion_tokens": resp.usage.completion_tokens or 0,
                    }
                return (resp.choices[0].message.content or "").strip()
            except Exception as exc:
                last_err = exc
                # If fatal auth, quota, or billing failure, immediately raise to failover without spinning
                if is_fatal_auth_or_quota_error(exc):
                    raise exc
                err_str = str(exc).lower()
                if "model_not_found" in err_str or "404" in err_str or "does not exist" in err_str:
                    continue
                raise exc

        raise last_err or RuntimeError(f"{self.lab.value} generation failed for {self.model}")


class GeminiProvider(LLMProvider):
    """Google Gemini adapter via native HTTP REST endpoint with automatic model fallback."""
    lab = Lab.GOOGLE

    def __init__(self, model: str = "gemini-3-flash-preview", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.fallback_models = ["gemini-3-flash-preview", "gemini-flash-lite-latest"]
        self.last_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        client = get_shared_http_client()
        models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
        last_err: Exception | None = None

        for m in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{"parts": [{"text": user_prompt}]}],
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "generationConfig": {
                        "temperature": temperature,
                        "responseMimeType": "application/json" if "json" in system_prompt.lower() else "text/plain",
                    },
                }
                resp = await client.post(url, json=payload)
                if resp.status_code in (404, 429, 503) or "not_found" in resp.text.lower() or "demand" in resp.text.lower() or "resource_exhausted" in resp.text.lower():
                    continue
                resp.raise_for_status()
                data = resp.json()
                usage_meta = data.get("usageMetadata", {})
                self.last_usage = {
                    "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                    "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                }
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts).strip()
                    if text:
                        self.model = m
                        return text
            except Exception as exc:
                last_err = exc
                err_lower = str(exc).lower()
                if "404" in err_lower or "503" in err_lower or "429" in err_lower or "not_found" in err_lower or "resource_exhausted" in err_lower:
                    continue
                if is_fatal_auth_or_quota_error(exc):
                    raise exc
                raise exc

        raise last_err or RuntimeError(f"Gemini generation failed for {self.model}")


class OllamaProvider(LLMProvider):
    """Local LLM adapter targeting Ollama or local vLLM OpenAI-compatible endpoint."""
    lab = Lab.OLLAMA

    def __init__(
        self,
        model: str = "llama3.2:latest",
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "ollama"
        self.fallback_models = ["llama3.2:latest", "llama3.2", "llama3.1", "mistral", "deepseek-r1"]
        self.last_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=get_shared_http_client(),
            max_retries=0,
        )
        models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
        last_err: Exception | None = None

        for m in models_to_try:
            try:
                resp = await client.chat.completions.create(
                    model=m,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                self.model = m
                if resp.usage:
                    self.last_usage = {
                        "prompt_tokens": resp.usage.prompt_tokens or 0,
                        "completion_tokens": resp.usage.completion_tokens or 0,
                    }
                return (resp.choices[0].message.content or "").strip()
            except Exception as exc:
                last_err = exc
                if is_fatal_auth_or_quota_error(exc):
                    raise exc
                err_str = str(exc).lower()
                if "model_not_found" in err_str or "404" in err_str or "does not exist" in err_str:
                    continue
                raise exc

        raise last_err or RuntimeError(f"Ollama generation failed for {self.model}")


