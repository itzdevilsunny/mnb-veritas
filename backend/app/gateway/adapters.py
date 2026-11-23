from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from app.gateway.base import LLMProvider
from app.models.schemas import Lab

logger = logging.getLogger("veritas.gateway.adapters")


class MockProvider(LLMProvider):
    """
    Offline deterministic provider used when external API keys are missing,
    or during integration tests and offline demonstrations.
    """

    def __init__(self, lab: Lab, model: str, canned_response: str | None = None) -> None:
        self.lab = lab
        self.model = model
        self.canned_response = canned_response

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if self.canned_response is not None:
            return self.canned_response

        # Realistic async processing delay when running outside pytest test suites
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            await asyncio.sleep(0.65)

        # Cross-lab auditor check
        if "compliance auditor" in system_prompt.lower() or "audit" in system_prompt.lower():
            return json.dumps({
                "supported": True,
                "reason": "Claim strictly entailed by source quote."
            })

        question_text = (
            user_prompt.split("Approved Sources:")[0].lower()
            if "Approved Sources:" in user_prompt
            else user_prompt.lower()
        )

        # Grounded dynamic extraction from all candidate source blocks in prompt
        blocks = re.findall(r"\[DOC_ID:\s*([^\|\s\]]+)[^\]]*\]\s*([^\[]+)", user_prompt)
        query_words = set(re.findall(r"[a-zA-Z0-9]{3,}", question_text))

        best_sentence: str | None = None
        best_doc_id: str | None = None
        best_score = -1.0

        for doc_id, snippet in blocks:
            doc_id = doc_id.strip()
            raw_sentences = re.split(r"(?<!\d)\.(?!\d)|\n+", snippet)
            for s in raw_sentences:
                s_clean = s.strip()
                if len(s_clean) < 12:
                    continue
                s_words = set(re.findall(r"[a-zA-Z0-9]{3,}", s_clean.lower()))
                overlap = len(query_words & s_words)
                if overlap > 0:
                    q_nums = set(re.findall(r"\d+", question_text))
                    s_nums = set(re.findall(r"\d+", s_clean))
                    num_bonus = 2.0 * len(q_nums & s_nums)
                    score = overlap + num_bonus
                    if score > best_score:
                        best_score = score
                        best_sentence = s_clean
                        best_doc_id = doc_id

        if best_sentence and best_doc_id:
            return json.dumps({
                "draft_answer": best_sentence,
                "claims": [
                    {
                        "claim_id": "CLM-01",
                        "claim_text": best_sentence,
                        "is_factual": True,
                        "verbatim_quote": best_sentence,
                        "cited_doc_id": best_doc_id,
                    }
                ]
            })

        return json.dumps({
            "draft_answer": "No answer possible",
            "claims": []
        })


class AnthropicProvider(LLMProvider):
    lab = Lab.ANTHROPIC

    def __init__(self, model: str = "claude-3-5-sonnet-20241022", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key)
        # Attempt requested model, falling back to production sonnet if alias is unrecognized
        models_to_try = [self.model, "claude-3-5-sonnet-20241022", "claude-3-5-sonnet-latest"]
        last_err: Exception | None = None

        for m in models_to_try:
            try:
                msg = await client.messages.create(
                    model=m,
                    max_tokens=2048,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                blocks = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
                self.model = m
                return "\n".join(blocks).strip()
            except Exception as exc:
                last_err = exc
                if "not_found" in str(exc).lower() or "404" in str(exc):
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

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError(f"API key missing for provider {self.lab.value}")
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
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
                return (resp.choices[0].message.content or "").strip()
            except Exception as exc:
                last_err = exc
                err_str = str(exc).lower()
                if "model_not_found" in err_str or "404" in err_str or "does not exist" in err_str:
                    continue
                raise exc

        raise last_err or RuntimeError(f"{self.lab.value} generation failed for {self.model}")


class GeminiProvider(LLMProvider):
    """Google Gemini adapter via OpenAI-compatible endpoint with automatic model fallback."""
    lab = Lab.GOOGLE

    def __init__(self, model: str = "gemini-1.5-flash", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.fallback_models = ["gemini-1.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"]

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
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
                return (resp.choices[0].message.content or "").strip()
            except Exception as exc:
                last_err = exc
                err_str = str(exc).lower()
                if "not_found" in err_str or "404" in err_str or "does not exist" in err_str:
                    continue
                raise exc

        raise last_err or RuntimeError(f"Gemini generation failed for {self.model}")
