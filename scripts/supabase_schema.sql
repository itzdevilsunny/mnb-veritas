-- =====================================================================
-- MNB VERITAS — SUPABASE POSTGRESQL SCHEMA WITH PGVECTOR & PG_TRGM
-- Options A through D Parity Schema (Authority Tiers, Audit Chain, etc.)
-- Run this in the Supabase Dashboard SQL Editor:
-- https://supabase.com/dashboard/project/rzgbswkasiddobaaewrq/sql/new
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

-- Fast GIN Trigram index for lexical substring & trigram search
CREATE INDEX IF NOT EXISTS idx_veritas_sources_trgm ON veritas_sources USING gin (text gin_trgm_ops);

-- HNSW Vector Index for Cosine Similarity (S2 Hybrid Retrieval)
CREATE INDEX IF NOT EXISTS idx_veritas_sources_embedding ON veritas_sources USING hnsw (embedding vector_cosine_ops);

-- Indexes for temporal validity, authority tier, and document lookups
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
    estimated_cost_usd DOUBLE PRECISION DEFAULT 0.0,
    claim_audits JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    prev_hash VARCHAR(64),
    record_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_veritas_audit_logs_created_at ON veritas_audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_veritas_audit_logs_verdict ON veritas_audit_logs(verdict);
CREATE INDEX IF NOT EXISTS idx_veritas_audit_logs_record_hash ON veritas_audit_logs(record_hash);

-- 5. Safe Migration for Existing Databases (Idempotent ALTER TABLE statements)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'veritas_sources' AND column_name = 'authority_tier'
    ) THEN
        ALTER TABLE veritas_sources ADD COLUMN authority_tier VARCHAR(32) NOT NULL DEFAULT 'regulatory';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'veritas_app_keys' AND column_name = 'allowed_policies'
    ) THEN
        ALTER TABLE veritas_app_keys ADD COLUMN allowed_policies JSONB NOT NULL DEFAULT '["standard","balanced","strict"]'::jsonb;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'veritas_audit_logs' AND column_name = 'prev_hash'
    ) THEN
        ALTER TABLE veritas_audit_logs ADD COLUMN prev_hash VARCHAR(64);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'veritas_audit_logs' AND column_name = 'record_hash'
    ) THEN
        ALTER TABLE veritas_audit_logs ADD COLUMN record_hash VARCHAR(64);
    END IF;
END $$;

-- 6. Ensure Supabase Auth Roles exist (for portable execution on both vanilla Postgres & Supabase Cloud)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon;
    END IF;
END $$;

-- 7. Row Level Security (RLS) Policies
ALTER TABLE veritas_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE veritas_app_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE veritas_audit_logs ENABLE ROW LEVEL SECURITY;

-- Allow Service Role key full access to all operations
DROP POLICY IF EXISTS "Service Role Full Access Sources" ON veritas_sources;
CREATE POLICY "Service Role Full Access Sources" ON veritas_sources FOR ALL TO service_role USING (true);

DROP POLICY IF EXISTS "Service Role Full Access App Keys" ON veritas_app_keys;
CREATE POLICY "Service Role Full Access App Keys" ON veritas_app_keys FOR ALL TO service_role USING (true);

DROP POLICY IF EXISTS "Service Role Full Access Audit Logs" ON veritas_audit_logs;
CREATE POLICY "Service Role Full Access Audit Logs" ON veritas_audit_logs FOR ALL TO service_role USING (true);

-- Allow Public/Anon read-only access to active sources (optional)
DROP POLICY IF EXISTS "Anon Read Active Sources" ON veritas_sources;
CREATE POLICY "Anon Read Active Sources" ON veritas_sources FOR SELECT TO anon USING (is_active = true);
