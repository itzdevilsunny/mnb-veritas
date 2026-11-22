from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from app.core.supabase import SupabaseManager, get_supabase_manager


@pytest.mark.asyncio
async def test_supabase_manager_configuration():
    mgr = get_supabase_manager()
    assert mgr.base_url == "https://rzgbswkasiddobaaewrq.supabase.co"
    if mgr.secret_key:
        assert mgr.secret_key.startswith("sb_secret_")


@pytest.mark.asyncio
async def test_supabase_health_mocked():
    """Ensures SupabaseManager health logic handles 200 responses cleanly in CI."""
    mgr = get_supabase_manager()
    mock_resp_rest = AsyncMock(spec=httpx.Response)
    mock_resp_rest.status_code = 200

    mock_resp_jwks = AsyncMock(spec=httpx.Response)
    mock_resp_jwks.status_code = 200
    mock_resp_jwks.json.return_value = {"keys": [{"kid": "test-key-id"}]}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [mock_resp_rest, mock_resp_jwks]
        health = await mgr.check_health()
        assert health["configured"] is True
        assert health["rest_connected"] is True
        assert health["rest_status"] == 200
        assert health["status"] == "healthy"


@pytest.mark.asyncio
async def test_supabase_health_live():
    """Runs live check if secret key is present in environment, skips cleanly otherwise."""
    mgr = get_supabase_manager()
    if not mgr.secret_key:
        pytest.skip("SUPABASE_SECRET_KEY not set in current runner environment")

    health = await mgr.check_health()
    assert health["configured"] is True
    assert health["rest_connected"] is True
    assert health["rest_status"] == 200
    assert health["jwks_available"] is True
    assert health["status"] == "healthy"
