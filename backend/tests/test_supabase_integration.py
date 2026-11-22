from __future__ import annotations

import pytest
from app.core.supabase import get_supabase_manager


@pytest.mark.asyncio
async def test_supabase_manager_configuration():
    mgr = get_supabase_manager()
    assert mgr.is_configured is True
    assert mgr.base_url == "https://rzgbswkasiddobaaewrq.supabase.co"
    assert mgr.secret_key is not None
    assert mgr.secret_key.startswith("sb_secret_")


@pytest.mark.asyncio
async def test_supabase_health_live():
    mgr = get_supabase_manager()
    health = await mgr.check_health()
    assert health["configured"] is True
    assert health["rest_connected"] is True
    assert health["rest_status"] == 200
    assert health["jwks_available"] is True
    assert health["jwks_status"] == 200
    assert health["status"] == "healthy"
