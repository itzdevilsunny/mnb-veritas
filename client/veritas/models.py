from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    APPROVE = "APPROVE"
    QUALIFY = "QUALIFY"
    ABSTAIN = "ABSTAIN"
    ESCALATE = "ESCALATE"


class PolicyMode(str, Enum):
    STANDARD = "standard"
    BALANCED = "balanced"
    STRICT = "strict"


class ClaimAuditItem(BaseModel):
    claim_id: str
    claim_text: str
    is_factual: bool = True
    is_critical: bool = False
    quote_verified: bool = False
    source_expired: bool = False
    numeric_mismatch: bool = False
    fy_mismatch: bool = False
    cross_lab_supported: bool = False
    reasons: list[str] = Field(default_factory=list)
    matched_doc_id: str | None = None
    verbatim_quote: str | None = None
    page_number: int | None = None
    chunk_index: int | None = None


class VerifyTelemetry(BaseModel):
    primary_model: str
    auditor_model: str | None = None
    moe_route: str = "fast_extraction"
    circuit_state: str = "CLOSED"
    failover_triggered: bool = False
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    numeric_concord_pct: float = 100.0
    temporal_bound: str = "VALID"


class VerifyResult(BaseModel):
    audit_id: str
    verdict: Verdict
    answer: str
    policy_applied: PolicyMode
    telemetry: VerifyTelemetry
    claim_audits: list[ClaimAuditItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: str

    @property
    def is_approved(self) -> bool:
        return self.verdict == Verdict.APPROVE

    @property
    def is_abstained(self) -> bool:
        return self.verdict == Verdict.ABSTAIN

    @property
    def is_escalated(self) -> bool:
        return self.verdict == Verdict.ESCALATE

    @property
    def claims_count(self) -> int:
        return len(self.claim_audits)

    @property
    def verified_quotes_count(self) -> int:
        return sum(1 for c in self.claim_audits if c.quote_verified)


class BatchItemResult(BaseModel):
    index: int
    item_id: str | None = None
    success: bool = True
    result: VerifyResult | None = None
    error: str | None = None


class BatchSummary(BaseModel):
    total_items: int
    approved_count: int = 0
    abstained_count: int = 0
    qualified_count: int = 0
    escalated_count: int = 0
    error_count: int = 0
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0


class BatchVerifyResult(BaseModel):
    summary: BatchSummary
    results: list[BatchItemResult]

    @property
    def total(self) -> int:
        return self.summary.total_items

    @property
    def successful(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        return self.summary.error_count


class ChainStatus(BaseModel):
    valid: bool
    checked_count: int
    latest_record_hash: str | None = None
    first_broken_audit_id: str | None = None
    details: str


class ProviderHealth(BaseModel):
    status: str = "ok"
    redis_connected: bool = False
    providers: dict[str, Any] = Field(default_factory=dict)
    active_count: int = 0
    total_configured: int = 0


class StreamStageEvent(BaseModel):
    stage: int
    name: str
    message: str | None = None
    progress: int = 0
    report: dict[str, Any] | None = None
