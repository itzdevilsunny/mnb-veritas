from __future__ import annotations

import logging
from typing import Any
import httpx
from app.core.config import get_settings

logger = logging.getLogger("veritas.supabase")


class SupabaseManager:
    """
    Manages connection, health checks, and data synchronization with Supabase.
    Operates over the authenticated Supabase PostgREST API and Auth JWKS.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = (self.settings.SUPABASE_URL or "").rstrip("/")
        self.secret_key = self.settings.SUPABASE_SECRET_KEY
        self.publishable_key = (
            self.settings.SUPABASE_PUBLISHABLE_KEY
            or self.settings.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
        )
        self.jwks_url = self.settings.SUPABASE_JWKS_URL

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and (self.secret_key or self.publishable_key))

    def _get_headers(self, prefer_secret: bool = True) -> dict[str, str]:
        key = self.secret_key if (prefer_secret and self.secret_key) else self.publishable_key
        headers = {
            "apikey": key or "",
            "Authorization": f"Bearer {key or ''}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        return headers

    async def check_health(self) -> dict[str, Any]:
        """Verifies active connectivity to Supabase PostgREST and JWKS endpoints."""
        if not self.is_configured:
            return {
                "configured": False,
                "status": "unconfigured",
                "message": "Supabase URL or keys not configured in environment.",
            }

        result: dict[str, Any] = {
            "configured": True,
            "supabase_url": self.base_url,
            "has_secret_key": bool(self.secret_key),
            "has_publishable_key": bool(self.publishable_key),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. PostgREST Root Check
            rest_url = f"{self.base_url}/rest/v1/"
            try:
                resp = await client.get(rest_url, headers=self._get_headers(prefer_secret=True))
                result["rest_status"] = resp.status_code
                result["rest_connected"] = (resp.status_code == 200)
            except Exception as e:
                result["rest_status"] = None
                result["rest_connected"] = False
                result["rest_error"] = str(e)

            # 2. Auth JWKS Check
            if self.jwks_url:
                try:
                    jwks_resp = await client.get(self.jwks_url)
                    result["jwks_status"] = jwks_resp.status_code
                    result["jwks_available"] = (jwks_resp.status_code == 200)
                    if jwks_resp.status_code == 200:
                        keys = jwks_resp.json().get("keys", [])
                        result["jwks_keys_count"] = len(keys)
                except Exception as e:
                    result["jwks_available"] = False
                    result["jwks_error"] = str(e)

        result["status"] = "healthy" if result.get("rest_connected") else "degraded"
        return result

    async def insert_source(self, source_dict: dict[str, Any]) -> bool:
        """Mirror a VeritasSource record into Supabase veritas_sources table if present."""
        if not self.is_configured or not self.secret_key:
            return False

        url = f"{self.base_url}/rest/v1/veritas_sources"
        headers = self._get_headers(prefer_secret=True)
        headers["Prefer"] = "resolution=merge-duplicates"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=source_dict)
                if resp.status_code in (200, 201):
                    return True
                logger.warning("Supabase source insert returned %s: %s", resp.status_code, resp.text)
                return False
        except Exception as e:
            logger.warning("Supabase source sync skipped due to network/schema: %s", e)
            return False

    async def insert_audit_log(self, audit_dict: dict[str, Any]) -> bool:
        """Mirror an audit log entry into Supabase veritas_audit_logs table if present."""
        if not self.is_configured or not self.secret_key:
            return False

        url = f"{self.base_url}/rest/v1/veritas_audit_logs"
        headers = self._get_headers(prefer_secret=True)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=audit_dict)
                if resp.status_code in (200, 201):
                    return True
                logger.warning("Supabase audit insert returned %s: %s", resp.status_code, resp.text)
                return False
        except Exception as e:
            logger.warning("Supabase audit sync skipped due to network/schema: %s", e)
            return False


_manager: SupabaseManager | None = None


def get_supabase_manager() -> SupabaseManager:
    global _manager
    if _manager is None:
        _manager = SupabaseManager()
    return _manager
