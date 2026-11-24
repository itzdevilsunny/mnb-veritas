from __future__ import annotations

import hashlib
import json
import time
from datetime import date, datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.benchmark import BenchmarkRunRequest, BenchmarkSuiteReport, execute_forensic_benchmark
from app.services.alerting import dispatch_compliance_alert, send_test_webhook
from app.core.auth_rate_limit import (
    AuthenticatedClient,
    generate_app_key,
    verify_authenticated_client,
)
from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.supabase import get_supabase_manager
from app.gateway.circuit_breaker import get_circuit_breaker
from app.gateway.registry import build_default_router
from app.gateway.router import VeritasRouter
from app.ingestion.parser import extract_pdf_chunks
from app.models.db import VeritasAppKey, VeritasAuditLog, VeritasSource
from app.models.schemas import (
    AppKeyCreatedResponse,
    AppKeyCreateRequest,
    AppKeyOut,
    AuditLogListItem,
    GatewayTelemetry,
    HumanReviewRequest,
    HumanReviewResponse,
    Lab,
    SourceCreateRequest,
    SourceExpiryUpdateRequest,
    SourceOut,
    Verdict,
    VerifyApiRequest,
    VerifyApiResponse,
)
from app.pipeline.veritas_engine import SourceDoc, VeritasPipeline

router = APIRouter(prefix="/v1", tags=["veritas"])


def get_veritas_router() -> VeritasRouter:
    """Provides the multi-lab router singleton instance."""
    return build_default_router()


# =====================================================================
# PROVIDER HEALTH & CIRCUIT BREAKER ENDPOINTS
# =====================================================================

@router.get("/health/providers")
async def get_providers_health(
    router_inst: VeritasRouter = Depends(get_veritas_router),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> dict[str, Any]:
    """Returns live circuit breaker state and metadata for all multi-lab LLM providers."""
    status_data = await router_inst.circuit_breaker.get_all_status()
    # Enrich provider metadata with configured model and engine backend
    for lab_key, p_info in status_data.get("providers", {}).items():
        try:
            lab_enum = Lab(lab_key)
            provider = router_inst.providers.get(lab_enum)
            if provider:
                from app.gateway.adapters import MockProvider
                p_info["model"] = provider.model
                p_info["configured"] = True
                p_info["backend"] = "mock" if isinstance(provider, MockProvider) else "live_api"
            else:
                p_info["configured"] = False
                p_info["backend"] = "none"
        except Exception:
            pass

    providers_dict = status_data.get("providers", {})
    status_data["total_configured"] = len(providers_dict)
    status_data["active_count"] = sum(1 for p in providers_dict.values() if p.get("state") != "OPEN")
    return status_data


@router.post("/health/providers/{lab}/reset")
async def reset_provider_circuit(
    lab: str,
    router_inst: VeritasRouter = Depends(get_veritas_router),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> dict[str, Any]:
    """Manually resets the circuit breaker for a given lab to CLOSED."""
    try:
        lab_enum = Lab(lab.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid lab '{lab}'. Must be one of: anthropic, openai, google, xai.",
        )

    await router_inst.circuit_breaker.reset(lab_enum)
    return {
        "status": "ok",
        "message": f"Circuit for {lab_enum.value} reset to CLOSED.",
        "lab": lab_enum.value,
        "state": "CLOSED",
    }


@router.get("/health/supabase")
async def get_supabase_health(
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> dict[str, Any]:
    """Returns live connection and health status for Supabase integration."""
    mgr = get_supabase_manager()
    return await mgr.check_health()


def _serialize_source(row: VeritasSource, ref_date: date | None = None) -> SourceOut:
    today = ref_date or date.today()
    valid = row.is_active and (today >= row.valid_from) and (
        row.valid_until is None or today <= row.valid_until
    )
    meta = row.metadata_json or {}
    return SourceOut(
        id=row.id,
        doc_id=row.doc_id,
        title=row.title,
        text=row.text,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        is_primary=row.is_primary,
        is_active=row.is_active,
        is_currently_valid=valid,
        has_embedding=bool(row.embedding),
        page_count=meta.get("total_pages"),
        chunk_count=meta.get("chunk_index"),
        created_at=row.created_at,
    )


# =====================================================================
# SOURCE MANAGEMENT ENDPOINTS
# =====================================================================

@router.get("/sources", response_model=list[SourceOut])
async def list_sources(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> list[SourceOut]:
    stmt = select(VeritasSource).order_by(desc(VeritasSource.is_primary), desc(VeritasSource.created_at))
    if not include_inactive:
        stmt = stmt.where(VeritasSource.is_active.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return [_serialize_source(r) for r in rows]


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def upsert_source(
    payload: SourceCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> SourceOut:
    if payload.valid_until is not None and payload.valid_until < payload.valid_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="valid_until cannot precede valid_from",
        )

    existing = (
        await db.execute(select(VeritasSource).where(VeritasSource.doc_id == payload.doc_id))
    ).scalar_one_or_none()

    if existing:
        existing.title = payload.title
        existing.text = payload.text
        existing.valid_from = payload.valid_from
        existing.valid_until = payload.valid_until
        existing.is_primary = payload.is_primary
        existing.is_active = True
        existing.metadata_json = payload.metadata
        if payload.embedding is not None:
            existing.embedding = payload.embedding
        await db.commit()
        await db.refresh(existing)
        return _serialize_source(existing)

    row = VeritasSource(
        doc_id=payload.doc_id,
        title=payload.title,
        text=payload.text,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        is_primary=payload.is_primary,
        is_active=True,
        embedding=payload.embedding,
        metadata_json=payload.metadata,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _serialize_source(row)


@router.patch("/sources/{doc_id}/expiry", response_model=SourceOut)
async def update_source_expiry(
    doc_id: str,
    payload: SourceExpiryUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> SourceOut:
    row = (
        await db.execute(select(VeritasSource).where(VeritasSource.doc_id == doc_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source {doc_id} not found")

    if payload.valid_until is not None and payload.valid_until < row.valid_from:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="valid_until cannot precede valid_from")

    if payload.valid_until is not None:
        row.valid_until = payload.valid_until
    if payload.is_active is not None:
        row.is_active = payload.is_active

    await db.commit()
    await db.refresh(row)
    return _serialize_source(row)


@router.delete("/sources/cleanup-test-data", status_code=status.HTTP_200_OK)
async def cleanup_test_data(
    prefix: str = Query(default="", description="Optional custom prefix to delete, or deletes all default test prefixes"),
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> dict[str, Any]:
    """
    Cleans up synthetic test sources and associated audit logs generated during smoke/workflow/stress tests.
    Targets doc_ids starting with SMOKE-, WF_TEST-, TEMP-, ADVERSARIAL-, or specified prefix.
    """
    from sqlalchemy import or_

    test_prefixes = ["SMOKE-", "WF_TEST_", "TEMP_", "ADVERSARIAL_"]
    if prefix:
        test_prefixes.append(prefix)

    conditions = [VeritasSource.doc_id.startswith(p) for p in test_prefixes]
    source_stmt = select(VeritasSource).where(or_(*conditions))
    sources_to_delete = (await db.execute(source_stmt)).scalars().all()
    count_sources = len(sources_to_delete)

    for s in sources_to_delete:
        await db.delete(s)

    # Clean synthetic test audit records
    audit_conditions = [
        VeritasAuditLog.audit_id.startswith("smoke_"),
        VeritasAuditLog.audit_id.startswith("wf_"),
        VeritasAuditLog.audit_id.startswith("test_"),
        VeritasAuditLog.query_text.ilike("%smoke test%"),
        VeritasAuditLog.query_text.ilike("%standing deposit facility%"),
    ]
    audit_stmt = select(VeritasAuditLog).where(or_(*audit_conditions))
    audits_to_delete = (await db.execute(audit_stmt)).scalars().all()
    count_audits = len(audits_to_delete)

    for a in audits_to_delete:
        await db.delete(a)

    await db.commit()
    return {
        "status": "ok",
        "message": f"Cleaned up {count_sources} test sources and {count_audits} test audit logs.",
        "deleted_sources_count": count_sources,
        "deleted_audits_count": count_audits,
    }


@router.delete("/sources/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_source(
    doc_id: str,
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> None:
    row = (
        await db.execute(select(VeritasSource).where(VeritasSource.doc_id == doc_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source {doc_id} not found")
    row.is_active = False
    await db.commit()


@router.post("/sources/seed-presets", response_model=list[SourceOut])
async def seed_regulatory_presets(
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> list[SourceOut]:
    """Seeds official regulatory gazette circulars into active truth corpus."""
    presets = [
        {
            "doc_id": "doc_rbi_cyber_2026",
            "title": "RBI Master Direction on Cyber Security & Digital Payment Controls 2026",
            "text": "All regulated payment entities must enforce zero-trust identity architecture with maximum transaction velocity limits of ₹2,00,000 per hour for newly onboarded digital accounts during FY 2026-27.",
            "valid_from": date(2026, 1, 1),
            "valid_until": date(2028, 3, 31),
            "is_primary": True,
        },
        {
            "doc_id": "doc_sebi_esg_brsr_2026",
            "title": "SEBI Circular on Business Responsibility and Sustainability Reporting (BRSR Core)",
            "text": "Top 1000 listed entities by market capitalization must obtain reasonable assurance on BRSR Core indicators covering minimum 75 percent value chain footprints by end of FY 2026-27.",
            "valid_from": date(2026, 2, 1),
            "valid_until": date(2027, 12, 31),
            "is_primary": True,
        },
    ]
    out: list[SourceOut] = []
    for p in presets:
        existing = (await db.execute(select(VeritasSource).where(VeritasSource.doc_id == p["doc_id"]))).scalar_one_or_none()
        if existing:
            existing.title = p["title"]
            existing.text = p["text"]
            existing.valid_from = p["valid_from"]
            existing.valid_until = p["valid_until"]
            existing.is_primary = p["is_primary"]
            existing.is_active = True
            row = existing
        else:
            row = VeritasSource(**p)
            db.add(row)
        await db.commit()
        await db.refresh(row)
        out.append(_serialize_source(row))
    return out


# =====================================================================
# PDF UPLOAD & RECURSIVE CHUNKING
# =====================================================================

class UploadedChunkSummary(BaseModel):
    doc_id: str
    page_number: int
    chunk_index: int
    char_count: int
    preview: str


class PdfUploadResponse(BaseModel):
    base_doc_id: str
    title: str
    filename: str
    sha256: str
    total_pages: int
    chunks_created: int
    valid_from: date
    valid_until: date | None
    is_primary: bool
    chunks: list[UploadedChunkSummary]


@router.post("/sources/upload", response_model=PdfUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf_source(
    file: UploadFile = File(..., description="Official PDF truth document"),
    base_doc_id: str = Form(..., min_length=2, max_length=64),
    title: str = Form(..., min_length=2, max_length=255),
    valid_from: date = Form(...),
    valid_until: date | None = Form(default=None),
    is_primary: bool = Form(default=True),
    max_chars: int = Form(default=1800, ge=400, le=6000),
    overlap_chars: int = Form(default=200, ge=0, le=1000),
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> PdfUploadResponse:
    settings = get_settings()
    filename = file.filename or "uploaded.pdf"

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only valid PDF documents (.pdf) can be uploaded for chunking.",
        )

    content = await file.read()
    if len(content) > settings.MAX_PDF_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_PDF_BYTES // (1024*1024)}MB",
        )

    file_sha256 = hashlib.sha256(content).hexdigest()
    clean_base_id = base_doc_id.strip()

    try:
        total_pages, chunks = extract_pdf_chunks(
            pdf_bytes=content,
            base_doc_id=clean_base_id,
            base_title=title.strip(),
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse and chunk PDF: {str(e)}",
        )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded PDF contained no extractable textual content.",
        )
    summaries: list[UploadedChunkSummary] = []

    for chunk in chunks:
        existing = (
            await db.execute(select(VeritasSource).where(VeritasSource.doc_id == chunk.doc_id))
        ).scalar_one_or_none()

        chunk_title = f"{title.strip()} [p.{chunk.page_number} c.{chunk.chunk_index}]"
        meta = {
            "source_type": "pdf_chunk",
            "filename": filename,
            "sha256": file_sha256,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "char_count": chunk.char_count,
            "total_pages": total_pages,
            "base_doc_id": clean_base_id,
        }

        if existing:
            existing.title = chunk_title
            existing.text = chunk.text
            existing.valid_from = valid_from
            existing.valid_until = valid_until
            existing.is_primary = is_primary
            existing.is_active = True
            existing.metadata_json = meta
        else:
            db.add(
                VeritasSource(
                    doc_id=chunk.doc_id,
                    title=chunk_title,
                    text=chunk.text,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    is_primary=is_primary,
                    is_active=True,
                    metadata_json=meta,
                )
            )

        summaries.append(
            UploadedChunkSummary(
                doc_id=chunk.doc_id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                char_count=chunk.char_count,
                preview=chunk.text[:140] + ("..." if len(chunk.text) > 140 else ""),
            )
        )

    await db.commit()

    return PdfUploadResponse(
        base_doc_id=clean_base_id,
        title=title.strip(),
        filename=filename,
        sha256=file_sha256,
        total_pages=total_pages,
        chunks_created=len(summaries),
        valid_from=valid_from,
        valid_until=valid_until,
        is_primary=is_primary,
        chunks=summaries,
    )


# =====================================================================
# 5-STAGE VERIFICATION & PERSISTENT AUDIT LOG
# =====================================================================

@router.post("/verify", response_model=VerifyApiResponse)
async def verify_query(
    payload: VerifyApiRequest,
    db: AsyncSession = Depends(get_db_session),
    llm_router: VeritasRouter = Depends(get_veritas_router),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> VerifyApiResponse:
    start_time = time.perf_counter()

    # Enforce Layer 1 Auth Scoped Policy Profiles
    if payload.policy.value not in client.allowed_policies:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key '{client.key_prefix}' is restricted to policy profiles: {client.allowed_policies}. Policy '{payload.policy.value}' is not permitted.",
        )

    # 1. Fetch active truth sources from database
    stmt = select(VeritasSource).where(VeritasSource.is_active.is_(True))
    if payload.source_ids:
        stmt = stmt.where(VeritasSource.doc_id.in_(payload.source_ids))
    db_rows = (await db.execute(stmt)).scalars().all()

    merged_sources: dict[str, SourceDoc] = {
        r.doc_id: SourceDoc(
            doc_id=r.doc_id,
            title=r.title,
            text=r.text,
            valid_from=r.valid_from,
            valid_until=r.valid_until,
            is_primary=r.is_primary,
            metadata=r.metadata_json,
            embedding=r.embedding,
        )
        for r in db_rows
    }

    # 2. Merge optional inline test sources (from workbench input)
    if payload.inline_sources:
        for s in payload.inline_sources:
            merged_sources[s.doc_id] = SourceDoc(
                doc_id=s.doc_id,
                title=s.title,
                text=s.text,
                valid_from=s.valid_from,
                valid_until=s.valid_until,
                is_primary=s.is_primary,
                metadata=s.metadata,
                embedding=s.embedding,
            )

    # 3. Execute 5-Stage Verification Engine
    pipeline = VeritasPipeline(router=llm_router, sources=list(merged_sources.values()))
    report = await pipeline.run(
        query=payload.query,
        policy=payload.policy,
        preferred_labs=payload.preferred_labs,
        ref_date=payload.reference_date,
        source_ids=payload.source_ids,
    )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    # 4. Zero-PII Telemetry Logging (Prompts & sensitive texts are excluded)
    audit_id = f"aud_{hashlib.sha256(f'{payload.query}_{time.time()}'.encode()).hexdigest()[:8]}"
    telemetry = GatewayTelemetry(
        primary_model=report.model_used,
        auditor_model=report.auditor_model_used,
        failover_triggered=getattr(llm_router, "last_failover_occurred", False),
        latency_ms=elapsed_ms,
        prompt_tokens=report.tokens_in,
        completion_tokens=report.tokens_out,
        estimated_cost_usd=report.estimated_cost_usd,
        numeric_concord_pct=report.numeric_concord_pct,
        temporal_bound="VALID" if not any(c.source_expired for c in report.claim_audits) else "EXPIRED_FLAGGED",
    )

    # 5. Persist audit log
    claim_dicts = [c.model_dump() for c in report.claim_audits]
    audit_entry = VeritasAuditLog(
        audit_id=audit_id,
        query_text=payload.query,
        verdict=report.verdict.value,
        answer=report.answer,
        policy_applied=payload.policy.value,
        primary_model=report.model_used,
        auditor_model=report.auditor_model_used,
        failover_triggered=telemetry.failover_triggered,
        latency_ms=elapsed_ms,
        estimated_cost_usd=report.estimated_cost_usd,
        claim_audits=claim_dicts,
        warnings=report.warnings,
        created_at=datetime.now(),
    )
    db.add(audit_entry)
    await db.commit()

    settings = get_settings()
    if report.verdict in {Verdict.ABSTAIN, Verdict.QUALIFY} and settings.COMPLIANCE_WEBHOOK_URL:
        import asyncio
        asyncio.create_task(
            dispatch_compliance_alert(
                event_type=f"VERDICT_{report.verdict.value}",
                audit_id=audit_id,
                query_text=payload.query,
                verdict=report.verdict.value,
                policy_applied=payload.policy.value,
                reasons=report.warnings,
                model=report.model_used,
            )
        )

    return VerifyApiResponse(
        audit_id=audit_id,
        verdict=report.verdict,
        answer=report.answer,
        policy_applied=payload.policy,
        telemetry=telemetry,
        claim_audits=report.claim_audits,
        warnings=report.warnings,
        created_at=audit_entry.created_at,
    )


@router.post("/verify/stream")
async def verify_query_stream(
    payload: VerifyApiRequest,
    db: AsyncSession = Depends(get_db_session),
    llm_router: VeritasRouter = Depends(get_veritas_router),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
):
    """
    Streams Server-Sent Events (SSE) detailing each pipeline stage in real-time,
    ending with the full verification report and persisting telemetry to the audit log.
    """
    # Enforce Layer 1 Auth Scoped Policy Profiles
    if payload.policy.value not in client.allowed_policies:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key '{client.key_prefix}' is restricted to policy profiles: {client.allowed_policies}. Policy '{payload.policy.value}' is not permitted.",
        )
    db_sources = (await db.execute(select(VeritasSource).where(VeritasSource.is_active == True))).scalars().all()
    merged_sources: dict[str, SourceDoc] = {}
    for s in db_sources:
        merged_sources[s.doc_id] = SourceDoc(
            doc_id=s.doc_id,
            title=s.title,
            text=s.text,
            valid_from=s.valid_from,
            valid_until=s.valid_until,
            is_primary=s.is_primary,
            metadata=s.metadata_json or {},
        )

    if payload.inline_sources:
        for s in payload.inline_sources:
            merged_sources[s.doc_id] = SourceDoc(
                doc_id=s.doc_id,
                title=s.title,
                text=s.text,
                valid_from=s.valid_from,
                valid_until=s.valid_until,
                is_primary=s.is_primary,
                metadata=s.metadata,
            )

    start_time = time.perf_counter()
    pipeline = VeritasPipeline(router=llm_router, sources=list(merged_sources.values()))

    async def event_generator():
        final_event = None
        async for event in pipeline.run_stream(
            query=payload.query,
            policy=payload.policy,
            preferred_labs=payload.preferred_labs,
            ref_date=payload.reference_date,
            source_ids=payload.source_ids,
        ):
            final_event = event
            yield f"data: {json.dumps(event, default=str)}\n\n"

        if final_event and final_event.get("stage") == 5:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            rep = final_event.get("report", {})
            audit_id = f"aud_{hashlib.sha256(f'{payload.query}_{time.time()}'.encode()).hexdigest()[:8]}"
            claim_audits_raw = rep.get("claim_audits", [])
            telemetry = GatewayTelemetry(
                primary_model=rep.get("model_used", "unknown"),
                auditor_model=rep.get("auditor_model_used"),
                failover_triggered=getattr(llm_router, "last_failover_occurred", False),
                latency_ms=elapsed_ms,
                prompt_tokens=rep.get("tokens_in", 0),
                completion_tokens=rep.get("tokens_out", 0),
                estimated_cost_usd=rep.get("estimated_cost_usd", 0.0),
                numeric_concord_pct=rep.get("numeric_concord_pct", 100.0),
                temporal_bound="VALID" if not any(c.get("source_expired") for c in claim_audits_raw) else "EXPIRED_FLAGGED",
            )
            audit_entry = VeritasAuditLog(
                audit_id=audit_id,
                query_text=payload.query,
                verdict=rep.get("verdict", "ABSTAIN"),
                answer=rep.get("answer", ""),
                policy_applied=payload.policy.value,
                primary_model=telemetry.primary_model,
                auditor_model=telemetry.auditor_model,
                failover_triggered=telemetry.failover_triggered,
                latency_ms=elapsed_ms,
                estimated_cost_usd=rep.get("estimated_cost_usd", 0.0),
                claim_audits=claim_audits_raw,
                warnings=rep.get("warnings", []),
                created_at=datetime.now(),
            )
            db.add(audit_entry)
            await db.commit()

            result_out = {
                "audit_id": audit_id,
                "verdict": rep.get("verdict"),
                "answer": rep.get("answer"),
                "policy_applied": payload.policy.value,
                "telemetry": telemetry.model_dump(),
                "claim_audits": claim_audits_raw,
                "warnings": rep.get("warnings", []),
                "created_at": audit_entry.created_at.isoformat(),
            }
            yield f"data: {json.dumps({'stage': 5, 'name': 'COMPLETE', 'progress': 100, 'result': result_out}, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# =====================================================================
# AUDIT LOG QUERY ENDPOINTS
# =====================================================================

@router.get("/audits", response_model=list[AuditLogListItem])
async def list_audits(
    verdict: str | None = Query(default=None, description="Filter by APPROVE, QUALIFY, ABSTAIN, ESCALATE"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> list[AuditLogListItem]:
    stmt = select(VeritasAuditLog).order_by(desc(VeritasAuditLog.created_at)).limit(limit)
    if verdict:
        stmt = stmt.where(VeritasAuditLog.verdict == verdict.upper())

    rows = (await db.execute(stmt)).scalars().all()
    return [
        AuditLogListItem(
            audit_id=r.audit_id,
            query_text=r.query_text,
            verdict=r.verdict,
            answer=r.answer,
            policy_applied=r.policy_applied,
            primary_model=r.primary_model,
            auditor_model=r.auditor_model,
            latency_ms=r.latency_ms,
            estimated_cost_usd=r.estimated_cost_usd,
            claim_audits=r.claim_audits or [],
            warnings=r.warnings or [],
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/audits/{audit_id}/review", response_model=HumanReviewResponse)
async def review_escalated_audit(
    audit_id: str,
    payload: HumanReviewRequest,
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> HumanReviewResponse:
    """Human-in-the-loop compliance review sign-off for ESCALATE audits."""
    audit = (
        await db.execute(select(VeritasAuditLog).where(VeritasAuditLog.audit_id == audit_id))
    ).scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit {audit_id} not found")

    decision = payload.decision.upper().strip()
    if decision not in ["APPROVE", "REJECT"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Decision must be 'APPROVE' or 'REJECT'"
        )

    prev_verdict = audit.verdict
    now = datetime.now(timezone.utc)
    new_verdict = "APPROVE" if decision == "APPROVE" else "ABSTAIN"
    audit.verdict = new_verdict
    audit.warnings = (audit.warnings or []) + [
        f"Human Compliance Sign-Off ({decision}) by {payload.reviewer} at {now.isoformat()}: {payload.notes}"
    ]
    if decision == "REJECT":
        audit.answer = "No answer possible (Rejected by compliance officer during human escalation review)"

    await db.commit()
    await db.refresh(audit)
    return HumanReviewResponse(
        audit_id=audit.audit_id,
        previous_verdict=prev_verdict,
        new_verdict=new_verdict,
        reviewer=payload.reviewer,
        reviewed_at=now,
        notes=payload.notes,
        is_safe_to_publish=(new_verdict == "APPROVE"),
    )


# =====================================================================
# PER-APP API KEY MANAGEMENT ENDPOINTS
# =====================================================================

@router.post("/app-keys", response_model=AppKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_app_key(
    payload: AppKeyCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> AppKeyCreatedResponse:
    """Creates a per-app API key. Raw key is returned once and never stored in plaintext."""
    raw_key, key_prefix, sha256_hash = generate_app_key(
        app_name=payload.app_name, rate_limit=payload.rate_limit_per_minute
    )

    policies = [p.value for p in payload.allowed_policies] if payload.allowed_policies else ["standard", "balanced", "strict"]
    record = VeritasAppKey(
        app_name=payload.app_name.strip(),
        key_prefix=key_prefix,
        sha256_hash=sha256_hash,
        rate_limit_per_minute=payload.rate_limit_per_minute,
        allowed_policies=policies,
        is_active=True,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return AppKeyCreatedResponse(
        id=record.id,
        app_name=record.app_name,
        key_prefix=record.key_prefix,
        rate_limit_per_minute=record.rate_limit_per_minute,
        allowed_policies=record.allowed_policies,
        is_active=record.is_active,
        created_at=record.created_at,
        last_used_at=record.last_used_at,
        raw_key=raw_key,
    )


@router.get("/app-keys", response_model=list[AppKeyOut])
async def list_app_keys(
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> list[AppKeyOut]:
    """Lists registered per-app API keys (hashes and raw keys are excluded)."""
    stmt = select(VeritasAppKey).order_by(desc(VeritasAppKey.created_at))
    records = (await db.execute(stmt)).scalars().all()
    return [
        AppKeyOut(
            id=r.id,
            app_name=r.app_name,
            key_prefix=r.key_prefix,
            rate_limit_per_minute=r.rate_limit_per_minute,
            is_active=r.is_active,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
        )
        for r in records
    ]


@router.delete("/app-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_app_key(
    key_id: str,
    db: AsyncSession = Depends(get_db_session),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> None:
    """Revokes a per-app API key by deactivating it (accepts UUID id or key_prefix)."""
    record = (
        await db.execute(
            select(VeritasAppKey).where(
                (VeritasAppKey.id == key_id) | (VeritasAppKey.key_prefix == key_id)
            )
        )
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"App key {key_id} not found")
    record.is_active = False
    await db.commit()


# =====================================================================
# FORENSIC BENCHMARK SUITE ENDPOINTS
# =====================================================================

@router.post("/benchmark/run", response_model=BenchmarkSuiteReport)
async def run_benchmark_battery(
    payload: BenchmarkRunRequest | None = None,
    db: AsyncSession = Depends(get_db_session),
    llm_router: VeritasRouter = Depends(get_veritas_router),
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> BenchmarkSuiteReport:
    """Executes the standardized 5-point forensic verification benchmark battery plus any custom cases."""
    custom = payload.custom_cases if payload else None
    return await execute_forensic_benchmark(db=db, llm_router=llm_router, custom_cases=custom)


# =====================================================================
# COMPLIANCE ALERTING & WEBHOOK ENDPOINTS
# =====================================================================

class WebhookTestRequest(BaseModel):
    webhook_url: str


class WebhookTestResponse(BaseModel):
    success: bool
    message: str


@router.post("/compliance/webhook-test", response_model=WebhookTestResponse)
async def test_compliance_webhook(
    payload: WebhookTestRequest,
    client: AuthenticatedClient = Depends(verify_authenticated_client),
) -> WebhookTestResponse:
    """Dispatches a diagnostic verification ping to an outbound compliance webhook."""
    success, msg = await send_test_webhook(payload.webhook_url.strip())
    return WebhookTestResponse(success=success, message=msg)
