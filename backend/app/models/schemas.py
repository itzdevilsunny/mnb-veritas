from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator


class Lab(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    XAI = "xai"
    OLLAMA = "ollama"
    AUTO = "auto"


class PolicyMode(str, Enum):
    STANDARD = "standard"
    BALANCED = "balanced"
    STRICT = "strict"


class Verdict(str, Enum):
    APPROVE = "APPROVE"
    QUALIFY = "QUALIFY"
    ABSTAIN = "ABSTAIN"
    ESCALATE = "ESCALATE"


class AuthorityTier(str, Enum):
    STATUTORY = "statutory"
    REGULATORY = "regulatory"
    ADVISORY = "advisory"
    DRAFT = "draft"


@dataclass
class SourceDoc:
    doc_id: str
    title: str
    text: str
    valid_from: date
    valid_until: date | None = None
    is_primary: bool = True
    is_active: bool = True
    authority_tier: AuthorityTier | str = AuthorityTier.REGULATORY
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None

    def is_valid_on(self, ref_date: date) -> bool:
        if ref_date < self.valid_from:
            return False
        if self.valid_until is not None and ref_date > self.valid_until:
            return False
        return True


class ExtractedClaim(BaseModel):
    claim_id: str
    claim_text: str
    is_factual: bool = True
    is_critical: bool = False
    verbatim_quote: str | None = Field(
        default=None,
        description="Exact substring copied from the source text if supported.",
    )
    cited_doc_id: str | None = None


class ExtractionBundle(BaseModel):
    draft_answer: str
    claims: list[ExtractedClaim]


class ClaimAuditResult(BaseModel):
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


class VerificationReport(BaseModel):
    verdict: Verdict
    answer: str
    model_used: str
    auditor_model_used: str | None
    claim_audits: list[ClaimAuditResult]
    warnings: list[str] = Field(default_factory=list)
    numeric_concord_pct: float = 100.0
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost_usd: float = 0.0
    failure_reason: str | None = None


# --- API Request & Response Schemas ---

class SourceCreateRequest(BaseModel):
    doc_id: str = Field(..., min_length=2, max_length=64)
    title: str = Field(..., min_length=2, max_length=255)
    text: str = Field(..., min_length=5)
    valid_from: date
    valid_until: date | None = None
    is_primary: bool = True
    authority_tier: AuthorityTier | str = Field(
        default=AuthorityTier.REGULATORY,
        description="Source authority tier: statutory > regulatory > advisory > draft",
    )
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceExpiryUpdateRequest(BaseModel):
    valid_until: date | None = None
    is_active: bool | None = None


class SourceOut(BaseModel):
    id: str
    doc_id: str
    title: str
    text: str
    valid_from: date
    valid_until: date | None
    is_primary: bool
    is_active: bool
    is_currently_valid: bool
    authority_tier: str = "regulatory"
    has_embedding: bool = False
    page_count: int | None = None
    chunk_count: int | None = None
    created_at: datetime


class GatewayTelemetry(BaseModel):
    primary_model: str
    auditor_model: str | None = None
    moe_route: str = "fast_extraction"
    circuit_state: str = "CLOSED"
    failover_triggered: bool = False
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    numeric_concord_pct: float = 100.0
    temporal_bound: str = "VALID"
    failure_reason: str | None = None



class VerifyApiRequest(BaseModel):
    query: str = Field(..., min_length=2)
    policy: PolicyMode = PolicyMode.STRICT
    preferred_labs: list[Lab] | None = None
    reference_date: date | None = None
    inline_sources: list[SourceCreateRequest] | None = None
    source_ids: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_policy_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "policy_mode" in data and "policy" not in data:
                data["policy"] = data["policy_mode"]
        return data


class VerifyApiResponse(BaseModel):
    audit_id: str
    verdict: Verdict
    answer: str
    policy_applied: PolicyMode
    telemetry: GatewayTelemetry
    claim_audits: list[ClaimAuditResult]
    warnings: list[str]
    created_at: datetime


class AuditLogListItem(BaseModel):
    audit_id: str
    query_text: str
    verdict: str
    answer: str
    policy_applied: str
    primary_model: str
    auditor_model: str | None
    latency_ms: int
    estimated_cost_usd: float | None = None
    claim_audits: list[dict[str, Any]]
    warnings: list[str]
    created_at: datetime
    prev_hash: str | None = None
    record_hash: str | None = None


class AuditChainVerificationResponse(BaseModel):
    valid: bool
    checked_count: int
    latest_record_hash: str | None = None
    first_broken_audit_id: str | None = None
    details: str


# --- Batch Verification Schemas ---

class BatchVerifyItemRequest(BaseModel):
    item_id: str | None = None
    query: str = Field(..., min_length=2)
    policy: PolicyMode | None = None
    preferred_labs: list[Lab] | None = None
    reference_date: date | None = None
    source_ids: list[str] | None = None


class BatchVerifyRequest(BaseModel):
    items: list[BatchVerifyItemRequest] = Field(..., min_length=1, max_length=50)
    policy: PolicyMode = PolicyMode.STRICT
    preferred_labs: list[Lab] | None = None
    reference_date: date | None = None
    source_ids: list[str] | None = None
    concurrency_limit: int = Field(default=5, ge=1, le=10)


class BatchVerifyItemResult(BaseModel):
    index: int
    item_id: str | None = None
    success: bool
    result: VerifyApiResponse | None = None
    error: str | None = None


class BatchVerifySummary(BaseModel):
    total_items: int
    approved_count: int = 0
    abstained_count: int = 0
    qualified_count: int = 0
    escalated_count: int = 0
    error_count: int = 0
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0


class BatchVerifyResponse(BaseModel):
    summary: BatchVerifySummary
    results: list[BatchVerifyItemResult]


# --- Compliance Certificate Schemas ---

class VerifiedQuoteClaim(BaseModel):
    claim_id: str
    verbatim_quote: str | None = None
    matched_doc_id: str | None = None
    quote_verified: bool = False
    numeric_mismatch: bool = False
    fy_mismatch: bool = False
    cross_lab_supported: bool = False


class ComplianceCertificateResponse(BaseModel):
    audit_id: str
    issued_at_utc: str
    verdict: str
    policy_applied: str
    safe_to_publish: bool
    primary_model: str
    auditor_model: str | None = None
    prev_hash: str | None = None
    record_hash: str | None = None
    chain_verified: bool
    latency_ms: int = 0
    estimated_cost_usd: float | None = None
    verified_quotes: list[VerifiedQuoteClaim] = Field(default_factory=list)
    certificate_seal_sha256: str
    issuer: str = "MNB Veritas Forensic Evidence Engine"


# --- App Key Schemas ---

class AppKeyCreateRequest(BaseModel):
    app_name: str = Field(..., min_length=2, max_length=64)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)
    allowed_policies: list[PolicyMode] = Field(
        default_factory=lambda: [PolicyMode.STANDARD, PolicyMode.BALANCED, PolicyMode.STRICT]
    )


class AppKeyOut(BaseModel):
    id: str
    app_name: str
    key_prefix: str
    rate_limit_per_minute: int
    allowed_policies: list[str] = Field(default_factory=lambda: ["standard", "balanced", "strict"])
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None


class AppKeyCreatedResponse(AppKeyOut):
    raw_key: str


# --- Human Escalation Review Schemas ---

class HumanReviewRequest(BaseModel):
    decision: str = Field(..., description="'APPROVE' or 'REJECT'")
    reviewer: str = Field(..., min_length=2)
    notes: str = Field(default="", max_length=1000)


class HumanReviewResponse(BaseModel):
    audit_id: str
    previous_verdict: str
    new_verdict: str
    reviewer: str
    reviewed_at: datetime
    notes: str
    is_safe_to_publish: bool
