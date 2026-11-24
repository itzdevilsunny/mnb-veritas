from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys for Multi-Lab Providers
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    XAI_API_KEY: str | None = None

    # Dynamic Model IDs per Lab (Fast Extraction vs Deep Audit Expert)
    DEFAULT_ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    FAST_ANTHROPIC_MODEL: str = "claude-3-5-haiku-20241022"
    AUDITOR_ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    DEFAULT_OPENAI_MODEL: str = "gpt-4o-mini"
    FAST_OPENAI_MODEL: str = "gpt-4o-mini"
    AUDITOR_OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MODEL: str = "gpt-4o-mini"

    DEFAULT_GEMINI_MODEL: str = "gemini-3-flash-preview"
    FAST_GEMINI_MODEL: str = "gemini-3-flash-preview"
    AUDITOR_GEMINI_MODEL: str = "gemini-flash-lite-latest"
    GEMINI_MODEL: str = "gemini-3-flash-preview"

    DEFAULT_XAI_MODEL: str = "grok-2"
    FAST_XAI_MODEL: str = "grok-2"
    AUDITOR_XAI_MODEL: str = "grok-2"
    XAI_MODEL: str = "grok-2"

    # Local LLM (Ollama / vLLM OpenAI-compatible)
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    DEFAULT_OLLAMA_MODEL: str = "llama3.2:latest"
    FAST_OLLAMA_MODEL: str = "llama3.2:latest"
    AUDITOR_OLLAMA_MODEL: str = "llama3.2:latest"
    OLLAMA_MODEL: str = "llama3.2:latest"

    # Governance & Auth
    DEFAULT_POLICY_MODE: str = "strict"
    VERITAS_API_KEY: str = "veritas-local-dev-key-2026"
    RATE_LIMIT_PER_MINUTE: int = 60

    # Database & Cache
    DATABASE_URL: str = "sqlite+aiosqlite:///./veritas.db"
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # Supabase Integration
    NEXT_PUBLIC_SUPABASE_URL: str | None = None
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: str | None = None
    SUPABASE_URL: str = "https://rzgbswkasiddobaaewrq.supabase.co"
    SUPABASE_PUBLISHABLE_KEY: str | None = None
    SUPABASE_SECRET_KEY: str | None = None
    SUPABASE_JWKS_URL: str = "https://rzgbswkasiddobaaewrq.supabase.co/auth/v1/.well-known/jwks.json"

    # Circuit Breaker thresholds
    CB_FAILURE_THRESHOLD: int = 1
    CB_COOLDOWN_SECONDS: float = 60.0

    # Hybrid Retrieval (S2) Settings
    MAX_CANDIDATE_SOURCES: int = 5
    RRF_K: int = 60
    EMBEDDING_DIM: int = 1536
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Pipeline Verification
    EXACT_SUBSTRING_REQUIRED: bool = True
    MAX_PDF_BYTES: int = 25 * 1024 * 1024  # 25MB

    # Compliance & Incident Alerting
    COMPLIANCE_WEBHOOK_URL: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
