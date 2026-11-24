from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Any
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, UserDefinedType

try:
    from pgvector.sqlalchemy import Vector as PgVector
except ImportError:
    PgVector = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SafeVector(TypeDecorator):
    """
    SQLAlchemy TypeDecorator that maps to pgvector.Vector(dim) in PostgreSQL
    and falls back cleanly to JSON in SQLite.
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 1536, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            if PgVector is not None:
                return dialect.type_descriptor(PgVector(self.dim))
            return dialect.type_descriptor(UserDefinedType())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return None
        return list(value)


class Base(DeclarativeBase):
    pass


class VeritasSource(Base):
    __tablename__ = "veritas_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    authority_tier: Mapped[str] = mapped_column(
        String(32), default="regulatory", server_default="regulatory", nullable=False
    )
    # Embedding vector column: Vector(1536) on PostgreSQL, JSON on SQLite
    embedding: Mapped[list[float] | None] = mapped_column(SafeVector(dim=1536), nullable=True)
    # JSON column works seamlessly across SQLite and PostgreSQL
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class VeritasAppKey(Base):
    """Per-App API Key store. Raw keys are never stored, only SHA-256 hash."""
    __tablename__ = "veritas_app_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_name: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    allowed_policies: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["standard", "balanced", "strict"], nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VeritasAuditLog(Base):
    __tablename__ = "veritas_audit_logs"

    audit_id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: f"aud_{uuid.uuid4().hex[:8]}"
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    policy_applied: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    primary_model: Mapped[str] = mapped_column(String(100), nullable=False)
    auditor_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failover_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, default=0.0035, nullable=True)
    claim_audits: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
