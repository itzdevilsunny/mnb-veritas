"""
MNB Veritas Official Python Client & SDK
Evidence-gated, anti-hallucination verification middleware.
"""

from __future__ import annotations

from veritas.client import VeritasClient, VeritasSyncClient
from veritas.models import (
    BatchVerifyResult,
    ChainStatus,
    ClaimAuditItem,
    PolicyMode,
    ProviderHealth,
    StreamStageEvent,
    Verdict,
    VerifyResult,
)

__version__ = "1.4.0"
__all__ = [
    "VeritasClient",
    "VeritasSyncClient",
    "VerifyResult",
    "BatchVerifyResult",
    "ChainStatus",
    "ProviderHealth",
    "StreamStageEvent",
    "ClaimAuditItem",
    "PolicyMode",
    "Verdict",
]
