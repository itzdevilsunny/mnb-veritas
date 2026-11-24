from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from typing import Any, Literal
import httpx

from veritas.models import (
    BatchItemResult,
    BatchSummary,
    BatchVerifyResult,
    ChainStatus,
    ClaimAuditItem,
    PolicyMode,
    ProviderHealth,
    StreamStageEvent,
    Verdict,
    VerifyResult,
    VerifyTelemetry,
)


class VeritasClient:
    """
    Official asynchronous Python client for MNB Veritas evidence-gated verification.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 45.0,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_url = (api_url or os.getenv("VERITAS_API_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.api_key = api_key or os.getenv("VERITAS_API_KEY") or "veritas-local-dev-key-2026"
        self.timeout = timeout
        self._custom_client = httpx_client
        self._internal_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._custom_client:
            return self._custom_client
        if self._internal_client is None or self._internal_client.is_closed:
            headers = {
                "Accept": "application/json",
                "X-Veritas-Key": self.api_key,
                "User-Agent": "veritas-python-sdk/1.4.0",
            }
            self._internal_client = httpx.AsyncClient(
                base_url=self.api_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._internal_client

    async def close(self) -> None:
        if self._internal_client and not self._internal_client.is_closed:
            await self._internal_client.aclose()

    async def __aenter__(self) -> VeritasClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def verify(
        self,
        query: str,
        policy: PolicyMode | str = "strict",
        reference_date: str | None = None,
        source_ids: list[str] | None = None,
        inline_sources: list[dict[str, Any]] | None = None,
    ) -> VerifyResult:
        """
        Executes synchronous multi-lab verification against approved truth sources.
        """
        client = await self._get_client()
        payload: dict[str, Any] = {
            "query": query.strip(),
            "policy": str(policy).lower(),
        }
        if reference_date:
            payload["reference_date"] = reference_date
        if source_ids:
            payload["source_ids"] = source_ids
        if inline_sources:
            payload["inline_sources"] = inline_sources

        res = await client.post("/v1/verify", json=payload)
        res.raise_for_status()
        data = res.json()
        return VerifyResult.model_validate(data)

    async def verify_batch(
        self,
        items: list[dict[str, Any]],
    ) -> BatchVerifyResult:
        """
        Executes bounded concurrent batch verification across up to 50 items.
        """
        client = await self._get_client()
        res = await client.post("/v1/verify/batch", json={"items": items})
        res.raise_for_status()
        data = res.json()
        return BatchVerifyResult.model_validate(data)

    async def verify_stream(
        self,
        query: str,
        policy: PolicyMode | str = "strict",
        reference_date: str | None = None,
    ) -> AsyncIterator[StreamStageEvent]:
        """
        Streams real-time 5-stage verification events via Server-Sent Events (SSE).
        """
        client = await self._get_client()
        payload = {
            "query": query.strip(),
            "policy": str(policy).lower(),
        }
        if reference_date:
            payload["reference_date"] = reference_date

        headers = {"Accept": "text/event-stream"}
        async with client.stream("POST", "/v1/verify/stream", json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data:"):
                    raw_data = line[5:].strip()
                    try:
                        event_dict = json.loads(raw_data)
                        yield StreamStageEvent.model_validate(event_dict)
                    except Exception:
                        continue

    async def download_certificate(
        self,
        audit_id: str,
        format: Literal["pdf", "json"] = "pdf",
    ) -> bytes | dict[str, Any]:
        """
        Downloads a signed compliance certificate as raw PDF bytes or canonical JSON seal.
        """
        client = await self._get_client()
        res = await client.get(f"/v1/audits/{audit_id}/certificate?format={format}")
        res.raise_for_status()
        if format == "pdf":
            return res.content
        return res.json()

    async def verify_chain(self) -> ChainStatus:
        """
        Verifies the cryptographic integrity of the append-only SHA-256 audit blockchain.
        """
        client = await self._get_client()
        res = await client.get("/v1/audits/verify-chain")
        res.raise_for_status()
        return ChainStatus.model_validate(res.json())

    async def get_provider_health(self) -> ProviderHealth:
        """
        Queries circuit breaker states and live provider readiness across all labs.
        """
        client = await self._get_client()
        res = await client.get("/v1/health/providers")
        res.raise_for_status()
        return ProviderHealth.model_validate(res.json())


class VeritasSyncClient:
    """
    Synchronous blocking wrapper around VeritasClient for scripts and traditional backends.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 45.0,
    ) -> None:
        self.async_client = VeritasClient(api_url=api_url, api_key=api_key, timeout=timeout)

    def verify(self, *args: Any, **kwargs: Any) -> VerifyResult:
        return asyncio.run(self.async_client.verify(*args, **kwargs))

    def verify_batch(self, *args: Any, **kwargs: Any) -> BatchVerifyResult:
        return asyncio.run(self.async_client.verify_batch(*args, **kwargs))

    def download_certificate(self, *args: Any, **kwargs: Any) -> bytes | dict[str, Any]:
        return asyncio.run(self.async_client.download_certificate(*args, **kwargs))

    def verify_chain(self) -> ChainStatus:
        return asyncio.run(self.async_client.verify_chain())

    def get_provider_health(self) -> ProviderHealth:
        return asyncio.run(self.async_client.get_provider_health())

    def close(self) -> None:
        asyncio.run(self.async_client.close())

    def __enter__(self) -> VeritasSyncClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
