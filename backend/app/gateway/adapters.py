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

        STOP_WORDS = {
            "what", "is", "the", "are", "for", "and", "with", "under", "explain",
            "current", "this", "that", "from", "into", "been", "have", "has", "does",
            "will", "would", "about", "which", "when", "where", "how", "per"
        }

        # Grounded dynamic extraction from all candidate source blocks in prompt
        blocks = re.findall(r"\[DOC_ID:\s*([^\|\s\]]+)[^\]]*\]\s*([^\[]+)", user_prompt)
        raw_words = set(re.findall(r"[a-zA-Z0-9]{3,}", question_text))
        query_words = {w for w in raw_words if w not in STOP_WORDS}

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
                s_words = set(re.findall(r"[a-zA-Z0-9]{3,}", s_clean.lower())) - STOP_WORDS
                overlap = len(query_words & s_words)
                # Require genuine topical content overlap (at least 2 non-stopword tokens)
                if overlap >= 2:
                    q_nums = set(re.findall(r"\d+", question_text))
                    s_nums = set(re.findall(r"\d+", s_clean))
                    num_bonus = 1.5 * len(q_nums & s_nums)
                    score = overlap + num_bonus
                    if score > best_score:
                        best_score = score
                        best_sentence = s_clean
                        best_doc_id = doc_id

        # Require meaningful semantic content overlap
        if best_sentence and best_doc_id and best_score >= 2.0:
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

        import httpx
        models_to_try = [self.model, "claude-3-5-sonnet-20241022", "claude-3-5-sonnet-latest"]
        last_err: Exception | None = None

        for m in models_to_try:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
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
                    blocks = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
                    self.model = m
                    return "\n".join(blocks).strip()
            except Exception as exc:
                last_err = exc
                if "404" in str(exc) or "not_found" in str(exc).lower():
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
    """Google Gemini adapter via native HTTP REST endpoint with automatic model fallback."""
    lab = Lab.GOOGLE

    def __init__(self, model: str = "gemini-1.5-flash", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.fallback_models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        import httpx
        models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
        last_err: Exception | None = None

        for m in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{"parts": [{"text": user_prompt}]}],
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "generationConfig": {"temperature": temperature},
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 404 or "not_found" in resp.text.lower():
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts).strip()
                        if text:
                            self.model = m
                            return text
            except Exception as exc:
                last_err = exc
                if "404" in str(exc) or "not_found" in str(exc).lower():
                    continue
                raise exc

        raise last_err or RuntimeError(f"Gemini generation failed for {self.model}")
