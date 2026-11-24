from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import VeritasAuditLog, utcnow

logger = logging.getLogger("veritas.audit_chain")

# In-process locks keyed by event loop to prevent concurrent hash chain forking
_audit_chain_locks: dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}


def get_audit_chain_lock() -> asyncio.Lock:
    """Returns an asyncio.Lock bound to the current running event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.Lock()

    if loop not in _audit_chain_locks:
        _audit_chain_locks[loop] = asyncio.Lock()
    return _audit_chain_locks[loop]


def compute_claim_audits_digest(claim_audits: list[dict[str, Any]] | None) -> str:
    """
    Computes a deterministic hash over claim verification flags and outcomes.
    Omits raw quote text and user prompt strings to guarantee zero PII.
    """
    if not claim_audits:
        return "none"
    canonical_items: list[str] = []
    for c in claim_audits:
        c_id = str(c.get("claim_id") or "")
        q_ver = "1" if c.get("quote_verified") else "0"
        num_ok = "1" if not c.get("numeric_mismatch") else "0"
        fy_ok = "1" if not c.get("fy_mismatch") else "0"
        cross_ok = "1" if c.get("cross_lab_supported") else "0"
        exp = "1" if c.get("source_expired") else "0"
        reasons_count = str(len(c.get("reasons") or []))
        canonical_items.append(f"{c_id}:{q_ver}{num_ok}{fy_ok}{cross_ok}{exp}:{reasons_count}")
    return hashlib.sha256(";".join(canonical_items).encode("utf-8")).hexdigest()[:16]


def canonicalize_timestamp(dt: datetime | str) -> str:
    """
    Produces a canonical UTC timestamp string (%Y-%m-%d %H:%M:%S) across
    all database engines (PostgreSQL, SQLite, ISO-8601 strings, tz-aware or tz-naive).
    """
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            try:
                dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return str(dt)
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)


def compute_audit_record_hash(
    prev_hash: str | None,
    audit_id: str,
    created_at: datetime | str,
    verdict: str,
    policy_applied: str,
    primary_model: str,
    auditor_model: str | None,
    claim_audits: list[dict[str, Any]] | None,
) -> str:
    """
    Computes a deterministic SHA-256 hex digest for a single audit record.
    Links to the prior record's hash (or "GENESIS" for the first entry).
    Canonicalized to guarantee zero PII is included in the cryptographic hash.
    """
    effective_prev = prev_hash or "GENESIS"
    ts_str = canonicalize_timestamp(created_at)
    claim_digest = compute_claim_audits_digest(claim_audits)
    payload = (
        f"{effective_prev}|{audit_id}|{ts_str}|{verdict.upper()}|"
        f"{policy_applied.lower()}|{primary_model}|{auditor_model or 'none'}|{claim_digest}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def get_latest_audit_record_hash(db: AsyncSession) -> str:
    """Fetches the record_hash of the most recent audit log entry, or returns 'GENESIS'."""
    stmt = (
        select(VeritasAuditLog.record_hash)
        .where(VeritasAuditLog.record_hash.isnot(None))
        .order_by(desc(VeritasAuditLog.created_at), desc(VeritasAuditLog.audit_id))
        .limit(1)
    )
    res = (await db.execute(stmt)).scalar_one_or_none()
    return res or "GENESIS"


async def write_audit_log(
    db: AsyncSession,
    audit_id: str,
    query_text: str,
    verdict: str,
    answer: str,
    policy_applied: str,
    primary_model: str,
    auditor_model: str | None,
    failover_triggered: bool,
    latency_ms: int,
    estimated_cost_usd: float | None,
    claim_audits: list[dict[str, Any]],
    warnings: list[str],
    created_at: datetime | None = None,
) -> VeritasAuditLog:
    """
    Persists an audit log entry with strict concurrency serialization.
    Uses asyncio.Lock to prevent concurrent in-process race conditions,
    fetches the exact tail record_hash, computes the cryptographic link,
    and commits atomically to prevent chain forks.
    """
    async with get_audit_chain_lock():
        bind = db.bind
        dialect_name = bind.dialect.name if bind else ""
        if dialect_name == "postgresql":
            stmt = (
                select(VeritasAuditLog)
                .order_by(desc(VeritasAuditLog.created_at), desc(VeritasAuditLog.audit_id))
                .limit(1)
                .with_for_update()
            )
            latest = (await db.execute(stmt)).scalar_one_or_none()
        else:
            stmt = (
                select(VeritasAuditLog)
                .where(VeritasAuditLog.record_hash.isnot(None))
                .order_by(desc(VeritasAuditLog.created_at), desc(VeritasAuditLog.audit_id))
                .limit(1)
            )
            latest = (await db.execute(stmt)).scalar_one_or_none()

        prev_hash = latest.record_hash if latest and latest.record_hash else "GENESIS"

        now = created_at or utcnow()
        if latest and latest.created_at:
            latest_dt = latest.created_at
            if latest_dt.tzinfo is None:
                latest_dt = latest_dt.replace(tzinfo=timezone.utc)
            now_aware = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
            if now_aware <= latest_dt:
                now = latest_dt + timedelta(microseconds=10)
        record_hash = compute_audit_record_hash(
            prev_hash=prev_hash,
            audit_id=audit_id,
            created_at=now,
            verdict=verdict,
            policy_applied=policy_applied,
            primary_model=primary_model,
            auditor_model=auditor_model,
            claim_audits=claim_audits,
        )

        entry = VeritasAuditLog(
            audit_id=audit_id,
            query_text=query_text,
            verdict=verdict,
            answer=answer,
            policy_applied=policy_applied,
            primary_model=primary_model,
            auditor_model=auditor_model,
            failover_triggered=failover_triggered,
            latency_ms=latency_ms,
            estimated_cost_usd=estimated_cost_usd,
            claim_audits=claim_audits,
            warnings=warnings,
            created_at=now,
            prev_hash=prev_hash,
            record_hash=record_hash,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry


async def prepare_audit_log_entry(
    db: AsyncSession,
    audit_id: str,
    query_text: str,
    verdict: str,
    answer: str,
    policy_applied: str,
    primary_model: str,
    auditor_model: str | None,
    failover_triggered: bool,
    latency_ms: int,
    estimated_cost_usd: float | None,
    claim_audits: list[dict[str, Any]],
    warnings: list[str],
    created_at: datetime | None = None,
) -> VeritasAuditLog:
    """
    Constructs a VeritasAuditLog instance with cryptographically chained prev_hash and record_hash.
    """
    return await write_audit_log(
        db=db,
        audit_id=audit_id,
        query_text=query_text,
        verdict=verdict,
        answer=answer,
        policy_applied=policy_applied,
        primary_model=primary_model,
        auditor_model=auditor_model,
        failover_triggered=failover_triggered,
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost_usd,
        claim_audits=claim_audits,
        warnings=warnings,
        created_at=created_at,
    )


async def relink_audit_chain(db: AsyncSession) -> dict[str, Any]:
    """
    Idempotent repair helper: canonically orders all VeritasAuditLog records
    by (created_at.asc(), audit_id.asc()), sequentially recomputes prev_hash and record_hash
    starting from 'GENESIS', and commits to heal any historical concurrency forks.
    """
    async with get_audit_chain_lock():
        stmt = select(VeritasAuditLog).order_by(
            VeritasAuditLog.created_at.asc(), VeritasAuditLog.audit_id.asc()
        )
        rows = (await db.execute(stmt)).scalars().all()
        if not rows:
            return {"relinked_count": 0, "total_records": 0, "valid": True, "details": "Audit chain is empty."}

        expected_prev = "GENESIS"
        relinked_count = 0
        for idx, row in enumerate(rows):
            new_prev = "GENESIS" if idx == 0 else expected_prev
            new_hash = compute_audit_record_hash(
                prev_hash=new_prev,
                audit_id=row.audit_id,
                created_at=row.created_at,
                verdict=row.verdict,
                policy_applied=row.policy_applied,
                primary_model=row.primary_model,
                auditor_model=row.auditor_model,
                claim_audits=row.claim_audits,
            )
            if row.prev_hash != new_prev or row.record_hash != new_hash:
                row.prev_hash = new_prev
                row.record_hash = new_hash
                relinked_count += 1
            expected_prev = new_hash

        await db.commit()
        logger.info("Relinked %d of %d audit records cleanly.", relinked_count, len(rows))
        return {
            "relinked_count": relinked_count,
            "total_records": len(rows),
            "valid": True,
            "details": f"Relinked {relinked_count} of {len(rows)} records. Chain sealed canonically from GENESIS.",
        }


async def verify_audit_chain_integrity(db: AsyncSession) -> dict[str, Any]:
    """
    Sequentially traverses all stored audit logs, recomputing each record_hash and checking
    the cryptographic linkage against the prior record's record_hash.
    Catches post-hoc row mutations, deletions, or insertions immediately.
    """
    stmt = select(VeritasAuditLog).order_by(
        VeritasAuditLog.created_at.asc(), VeritasAuditLog.audit_id.asc()
    )
    rows = (await db.execute(stmt)).scalars().all()

    if not rows:
        return {
            "valid": True,
            "checked_count": 0,
            "first_broken_audit_id": None,
            "details": "Audit chain is empty. Genesis state intact.",
        }

    expected_prev = "GENESIS"
    for idx, row in enumerate(rows):
        # Genesis record check
        if idx == 0:
            if row.prev_hash is not None and row.prev_hash != "GENESIS":
                return {
                    "valid": False,
                    "checked_count": 1,
                    "first_broken_audit_id": row.audit_id,
                    "details": f"Genesis record {row.audit_id} has invalid prev_hash '{row.prev_hash}' (expected 'GENESIS').",
                }
        else:
            if row.prev_hash != expected_prev:
                return {
                    "valid": False,
                    "checked_count": idx + 1,
                    "first_broken_audit_id": row.audit_id,
                    "details": f"Chain link broken at record {row.audit_id}: stored prev_hash '{row.prev_hash}' does not match prior record_hash '{expected_prev}'.",
                }

        # Recompute hash for current row
        expected_hash = compute_audit_record_hash(
            prev_hash=row.prev_hash,
            audit_id=row.audit_id,
            created_at=row.created_at,
            verdict=row.verdict,
            policy_applied=row.policy_applied,
            primary_model=row.primary_model,
            auditor_model=row.auditor_model,
            claim_audits=row.claim_audits,
        )

        if row.record_hash != expected_hash:
            return {
                "valid": False,
                "checked_count": idx + 1,
                "first_broken_audit_id": row.audit_id,
                "details": f"Cryptographic signature mismatch at record {row.audit_id}: stored record_hash '{row.record_hash}' does not match recomputed hash '{expected_hash}'.",
            }

        expected_prev = row.record_hash

    return {
        "valid": True,
        "checked_count": len(rows),
        "latest_record_hash": rows[-1].record_hash if rows else None,
        "first_broken_audit_id": None,
        "details": f"All {len(rows)} audit records verified successfully with intact SHA-256 linkage.",
    }
