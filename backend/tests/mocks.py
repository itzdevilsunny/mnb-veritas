from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Callable
from app.gateway.base import BaseLLMAdapter, GenerationResult, LLMProvider, ZeroPIITelemetry
from app.models.schemas import Lab


class MockProvider(LLMProvider):
    """
    Offline deterministic mock provider used EXCLUSIVELY inside backend/tests/
    for unit test isolation. Never instantiated or referenced in production app code.
    """

    def __init__(self, lab: Lab, model: str, canned_response: str | None = None) -> None:
        self.lab = lab
        self.model = model
        self.canned_response = canned_response

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if self.canned_response is not None:
            return self.canned_response

        if not os.environ.get("PYTEST_CURRENT_TEST"):
            await asyncio.sleep(0.04)

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
                if overlap >= 2:
                    q_nums = set(re.findall(r"\d+", question_text))
                    s_nums = set(re.findall(r"\d+", s_clean))
                    num_bonus = 1.5 * len(q_nums & s_nums)
                    score = overlap + num_bonus
                    if score > best_score:
                        best_score = score
                        best_sentence = s_clean
                        best_doc_id = doc_id

        if best_sentence:
            from app.pipeline.s3_examine_code import extract_fy_tokens, extract_scaled_quantities
            q_fy = extract_fy_tokens(question_text)
            s_fy = extract_fy_tokens(best_sentence)
            if q_fy and s_fy and q_fy != s_fy:
                best_sentence = None
                best_doc_id = None
                best_score = -1.0

        if best_sentence:
            q_quants = [v for v, u in extract_scaled_quantities(question_text) if u == "base_number"]
            s_quants = [v for v, u in extract_scaled_quantities(best_sentence) if u == "base_number"]
            if q_quants and s_quants:
                for q_val in q_quants:
                    if not any(abs(q_val - s_val) <= 1e-5 * max(1.0, abs(s_val)) for s_val in s_quants):
                        best_sentence = None
                        best_doc_id = None
                        best_score = -1.0
                        break

        if best_sentence and best_doc_id and best_score >= 2.0:
            is_crit = any(k in question_text for k in ["critical", "statutory", "escalat", "emergency"])
            return json.dumps({
                "draft_answer": best_sentence,
                "claims": [
                    {
                        "claim_id": "CLM-01",
                        "claim_text": best_sentence,
                        "is_factual": True,
                        "is_critical": is_crit,
                        "verbatim_quote": best_sentence,
                        "cited_doc_id": best_doc_id,
                    }
                ]
            })

        return json.dumps({
            "draft_answer": "No answer possible",
            "claims": []
        })


class MockAdapter(MockProvider):
    """
    Offline adapter compatible with both MockProvider and BaseLLMAdapter contracts for unit tests.
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
