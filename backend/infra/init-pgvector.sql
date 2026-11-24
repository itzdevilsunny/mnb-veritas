-- =====================================================================
-- MNB VERITAS — CONTAINERIZED POSTGRESQL INITIALIZATION SCRIPT
-- Automatically executed on fresh PostgreSQL volume creation:
-- /docker-entrypoint-initdb.d/init-pgvector.sql
-- =====================================================================

-- 1. Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Evidence Sources Table (S2 Hybrid Retrieval & S3 Ground Truth)
CREATE TABLE IF NOT EXISTS veritas_sources (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    doc_id VARCHAR(64) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    text TEXT NOT NULL,
    valid_from DATE NOT NULL,
    valid_until DATE,
    is_primary BOOLEAN NOT NULL DEFAULT true,
    is_active BOOLEAN NOT NULL DEFAULT true,
    authority_tier VARCHAR(32) NOT NULL DEFAULT 'regulatory',
    embedding vector(1536),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_veritas_sources_trgm ON veritas_sources USING gin (text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_veritas_sources_embedding ON veritas_sources USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_veritas_sources_doc_id ON veritas_sources(doc_id);
CREATE INDEX IF NOT EXISTS idx_veritas_sources_validity ON veritas_sources(is_active, valid_from, valid_until, is_primary);
CREATE INDEX IF NOT EXISTS idx_veritas_sources_authority ON veritas_sources(authority_tier);

-- 3. Application API Keys Table (Hashed Auth & Redis-backed Quotas)
CREATE TABLE IF NOT EXISTS veritas_app_keys (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    app_name VARCHAR(64) NOT NULL,
    key_prefix VARCHAR(16) NOT NULL,
    sha256_hash VARCHAR(64) UNIQUE NOT NULL,
    rate_limit_per_minute INT NOT NULL DEFAULT 60,
    allowed_policies JSONB NOT NULL DEFAULT '["standard","balanced","strict"]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_veritas_app_keys_hash ON veritas_app_keys(sha256_hash);

-- 4. Audit Log Table (Zero-PII Forensic Verification Blockchain)
CREATE TABLE IF NOT EXISTS veritas_audit_logs (
    audit_id VARCHAR(40) PRIMARY KEY,
    query_text TEXT NOT NULL,
    verdict VARCHAR(24) NOT NULL,
    answer TEXT NOT NULL,
    policy_applied VARCHAR(24) NOT NULL,
    primary_model VARCHAR(100) NOT NULL,
    auditor_model VARCHAR(100),
    failover_triggered BOOLEAN NOT NULL DEFAULT false,
    latency_ms INT NOT NULL,
    estimated_cost_usd DOUBLE PRECISION DEFAULT 0.0035,
    claim_audits JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    prev_hash VARCHAR(64),
    record_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_veritas_audit_logs_created_at ON veritas_audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_veritas_audit_logs_verdict ON veritas_audit_logs(verdict);
CREATE INDEX IF NOT EXISTS idx_veritas_audit_logs_record_hash ON veritas_audit_logs(record_hash);
