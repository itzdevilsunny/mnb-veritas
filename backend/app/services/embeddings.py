from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import re
from typing import Any

from app.core.config import get_settings
from app.gateway.http_pool import get_shared_http_client

logger = logging.getLogger("veritas.embeddings")


def deterministic_local_embedding(text: str, dim: int = 1536) -> list[float]:
    """
    Deterministically computes a normalized dense embedding vector from text
    using word-level and character n-gram feature hashing.
    Used as an offline zero-dependency, zero-cost, high-reliability fallback.
    """
    if not text:
        return [0.0] * dim

    vec = [0.0] * dim
    clean_text = text.lower().strip()

    # 1. Word token hashing
    tokens = re.findall(r"\w+", clean_text)
    for tok in tokens:
        idx = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16) % dim
        vec[idx] += 1.0

    # 2. Character 3-gram hashing for subword capture
    if len(clean_text) >= 3:
        for i in range(len(clean_text) - 2):
            tri = clean_text[i : i + 3]
            idx = int(hashlib.md5(tri.encode("utf-8")).hexdigest(), 16) % dim
            vec[idx] += 0.5

    # 3. L2 Normalization
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0.0:
        return [round(x / norm, 6) for x in vec]
    return vec


async def generate_embedding(
    text: str,
    model: str | None = None,
    dim: int | None = None,
) -> list[float]:
    """
    Generates an embedding vector for the supplied text.
    Uses EMBEDDING_MODEL from configuration / environment.
    If external API credentials are unconfigured, return errors, or rate limit,
    falls back cleanly to the deterministic local embedding generator.
    """
    settings = get_settings()
    target_model = model or getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small")
    target_dim = dim or getattr(settings, "EMBEDDING_DIM", 1536)

    # 1. Try OpenAI Embeddings if key configured
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and ("text-embedding" in target_model or "openai" in target_model.lower()):
        try:
            client = get_shared_http_client()
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json",
                },
                json={"input": text[:8000], "model": target_model},
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                emb = data.get("data", [{}])[0].get("embedding")
                if emb and isinstance(emb, list):
                    return emb
            else:
                logger.debug(
                    "OpenAI embeddings call returned %s (%s). Falling back to local embedding.",
                    resp.status_code,
                    resp.text[:100],
                )
        except Exception as exc:
            logger.debug("OpenAI embedding API unavailable (%s). Falling back to local embedding.", exc)

    # 2. Try Google Gemini Embeddings if key configured
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and ("gemini" in target_model or "embedding" in target_model):
        try:
            client = get_shared_http_client()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:embedContent?key={gemini_key}"
            resp = await client.post(
                url,
                json={"content": {"parts": [{"text": text[:8000]}]}},
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                emb = data.get("embedding", {}).get("values")
                if emb and isinstance(emb, list):
                    return emb
            else:
                logger.debug(
                    "Google embeddings call returned %s (%s). Falling back to local embedding.",
                    resp.status_code,
                    resp.text[:100],
                )
        except Exception as exc:
            logger.debug("Google embedding API unavailable (%s). Falling back to local embedding.", exc)

    # 3. Clean, zero-cost deterministic fallback
    return deterministic_local_embedding(text, dim=target_dim)


async def generate_embeddings_batch(
    texts: list[str],
    model: str | None = None,
    dim: int | None = None,
) -> list[list[float]]:
    """Concurrently generates embeddings for a batch of texts."""
    tasks = [generate_embedding(t, model=model, dim=dim) for t in texts]
    return await asyncio.gather(*tasks)
