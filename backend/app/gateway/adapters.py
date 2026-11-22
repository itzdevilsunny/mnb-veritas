from __future__ import annotations

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

        # Cross-lab auditor check
        if "compliance auditor" in system_prompt.lower() or "audit" in system_prompt.lower():
            return json.dumps({
                "supported": True,
                "reason": "Claim strictly entailed by source quote."
            })

        # Scenario Trigger 1: Green Hydrogen Mission
        question_text = (
            user_prompt.split("Approved Sources:")[0].lower()
            if "Approved Sources:" in user_prompt
            else user_prompt.lower()
        )

        if "offshore" in question_text or "lng" in question_text or "cayman" in question_text or "african" in question_text:
            return json.dumps({
                "draft_answer": "India has provided a sovereign bilateral credit guarantee facility for offshore African LNG liquefaction terminals.",
                "claims": [
                    {
                        "claim_id": "CLM-01",
                        "claim_text": "India has provided a sovereign bilateral credit guarantee facility for offshore African LNG liquefaction terminals.",
                        "is_factual": True,
                        "verbatim_quote": None,
                        "cited_doc_id": None,
                    }
                ]
            })

        if "green hydrogen" in question_text or "4,850" in question_text or "4850" in question_text:
            return json.dumps({
                "draft_answer": "The Ministry of Finance has sanctioned a total budgetary allocation of ₹4,850 crore for the National Green Hydrogen Mission for FY 2025-26 under the new outlay. The Strategic Interventions for Green Hydrogen Transition (SIGHT) program receives 68% of the total allocation, and expenditure execution is subject to quarterly review by the Ministry of New and Renewable Energy starting Q1 FY26.",
                "claims": [
                    {
                        "claim_id": "CLM-01",
                        "claim_text": "The Ministry of Finance has sanctioned a total budgetary allocation of ₹4,850 crore for the National Green Hydrogen Mission for FY 2025-26.",
                        "is_factual": True,
                        "verbatim_quote": "Cabinet approves continuation of National Green Hydrogen Mission with financial outlay of ₹4,850 crore specifically ear-marked for FY 2025-26 pilot electrolysers.",
                        "cited_doc_id": "doc_green_hydrogen_2024",
                    },
                    {
                        "claim_id": "CLM-02",
                        "claim_text": "The Strategic Interventions for Green Hydrogen Transition (SIGHT) program receives 68% of the total allocation.",
                        "is_factual": True,
                        "verbatim_quote": "Under component II (SIGHT), 68% of aggregate outlay shall be deployed across domestic electrolyser manufacturing incentives and green ammonia pilots.",
                        "cited_doc_id": "doc_green_hydrogen_2024",
                    },
                    {
                        "claim_id": "CLM-03",
                        "claim_text": "Expenditure execution is subject to quarterly review by the Ministry of New and Renewable Energy starting Q1 FY26.",
                        "is_factual": True,
                        "verbatim_quote": "Quarterly financial milestone reviews will be convened jointly by MNRE beginning Q1 of FY 2025-26.",
                        "cited_doc_id": "doc_budget_2025",
                    }
                ]
            })

        if "repo" in question_text or "cpi" in question_text or "rbi" in question_text:
            return json.dumps({
                "draft_answer": "The Monetary Policy Committee decided to keep the policy repo rate unchanged at 6.50% while projecting CPI inflation for FY25 at 4.5%.",
                "claims": [
                    {
                        "claim_id": "CLM-01",
                        "claim_text": "The MPC kept the policy repo rate unchanged at 6.50%.",
                        "is_factual": True,
                        "verbatim_quote": "The MPC decided to keep the policy repo rate unchanged at 6.50 per cent.",
                        "cited_doc_id": "doc_rbi_fy25",
                    },
                    {
                        "claim_id": "CLM-02",
                        "claim_text": "CPI inflation projection for FY25 is 4.5%.",
                        "is_factual": True,
                        "verbatim_quote": "CPI inflation for 2024-25 is projected at 4.5 per cent with Q4 at 4.4 per cent.",
                        "cited_doc_id": "doc_rbi_fy25",
                    }
                ]
            })

        # Grounded extraction attempt from provided context
        source_match = re.search(r"\[DOC_ID:\s*([^\]]+)[^\]]*\]\s*([^\[]+)", user_prompt)
        if source_match:
            doc_id = source_match.group(1).strip()
            source_snippet = source_match.group(2).strip()
            first_sentence = source_snippet.split(".")[0].strip() + "."
            return json.dumps({
                "draft_answer": first_sentence,
                "claims": [
                    {
                        "claim_id": "CLM-01",
                        "claim_text": first_sentence,
                        "is_factual": True,
                        "verbatim_quote": first_sentence,
                        "cited_doc_id": doc_id,
                    }
                ]
            })

        return json.dumps({
            "draft_answer": "No answer possible",
            "claims": []
        })


class AnthropicProvider(LLMProvider):
    lab = Lab.ANTHROPIC

    def __init__(self, model: str = "claude-sonnet-5-5", api_key: str | None = None) -> None:
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

    def __init__(self, model: str = "gemini-4-hydrogen", api_key: str | None = None) -> None:
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
