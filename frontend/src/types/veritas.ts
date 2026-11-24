export type LabProvider = "anthropic" | "openai" | "google" | "xai" | "ollama" | "auto";
export type PolicyMode = "standard" | "balanced" | "strict";
export type Verdict = "APPROVE" | "QUALIFY" | "ABSTAIN" | "ESCALATE";
export type VeritasVerdict = Verdict;

export type CrossLabStatus = "entailed" | "rejected" | "unavailable" | "skipped";
export type SourceStatus = "valid" | "expired" | "not_yet_valid" | "missing";
export type AuthorityTier = "statutory" | "regulatory" | "advisory" | "draft";

export interface SourceInput {
  doc_id: string;
  title: string;
  text: string;
  valid_from: string; // YYYY-MM-DD
  valid_until?: string | null;
  is_primary?: boolean;
  authority_tier?: AuthorityTier;
}

export type SourceDocumentInput = SourceInput;

export interface ManagedSource {
  id: string;
  doc_id: string;
  title: string;
  text: string;
  valid_from: string;
  valid_until: string | null;
  is_primary: boolean;
  is_active: boolean;
  is_currently_valid: boolean;
  authority_tier?: AuthorityTier | string;
  has_embedding?: boolean;
  page_count?: number | null;
  chunk_count?: number | null;
  created_at: string;
}

export type SourceRow = ManagedSource;

export interface ClaimAudit {
  claim_id: string;
  claim_text: string;
  is_factual: boolean;
  matched_doc_id: string | null;
  verbatim_quote: string | null;
  source_status?: SourceStatus;
  source_expired: boolean;
  quote_verified: boolean;
  numeric_mismatch: boolean;
  fy_mismatch: boolean;
  cross_lab_status?: CrossLabStatus;
  cross_lab_supported: boolean;
  included_in_answer?: boolean;
  reasons: string[];
  page_number?: number | null;
  chunk_index?: number | null;
}

export type ClaimAuditItem = ClaimAudit;

export interface GatewayTelemetry {
  primary_model: string;
  auditor_model: string | null;
  moe_route?: string;
  circuit_state?: string;
  failover_triggered: boolean;
  failed_attempts?: string[];
  latency_ms: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  estimated_cost_usd?: number;
  numeric_concord_pct?: number;
  temporal_bound?: string;
}

export interface VerifyRequest {
  query: string;
  policy?: PolicyMode;
  preferred_labs?: LabProvider[];
  reference_date?: string;
  inline_sources?: SourceInput[];
  source_ids?: string[];
}

export interface VerifyResponse {
  audit_id: string;
  verdict: Verdict;
  answer: string;
  policy_applied: PolicyMode;
  telemetry: GatewayTelemetry;
  claim_audits: ClaimAudit[];
  warnings: string[];
  created_at: string;
}

export interface AuditRow {
  audit_id: string;
  query_text: string;
  verdict: Verdict;
  answer: string;
  policy_applied: PolicyMode | string;
  primary_model: string;
  auditor_model: string | null;
  failover_triggered?: boolean;
  latency_ms: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  estimated_cost_usd?: number | null;
  claim_audits: ClaimAudit[];
  warnings: string[];
  created_at: string;
}

export type AuditLogItem = AuditRow;

export interface PdfUploadResult {
  base_doc_id: string;
  title?: string;
  filename: string;
  total_pages: number;
  chunks_created: number;
}

export type CircuitState = "CLOSED" | "OPEN" | "HALF_OPEN";

export interface ProviderHealth {
  lab: LabProvider;
  configured: boolean;
  model: string | null;
  state: CircuitState;
  consecutive_failures: number;
  retry_after_s: number;
  backend: string;
}

export interface ProvidersHealth {
  backend: string;
  redis_connected?: boolean;
  providers: ProviderHealth[];
}
