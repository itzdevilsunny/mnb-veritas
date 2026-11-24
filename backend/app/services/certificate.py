from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone
from typing import Any
import pymupdf as fitz

from app.models.db import VeritasAuditLog
from app.models.schemas import ComplianceCertificateResponse, VerifiedQuoteClaim


def compute_certificate_seal(
    audit_id: str,
    record_hash: str | None,
    prev_hash: str | None,
    verdict: str,
    policy_applied: str,
    primary_model: str,
    auditor_model: str | None,
    chain_verified: bool,
) -> str:
    """Computes a deterministic SHA-256 seal locking the certificate metadata."""
    payload = (
        f"{audit_id}|{record_hash or 'none'}|{prev_hash or 'none'}|"
        f"{verdict.upper()}|{policy_applied.lower()}|{primary_model}|"
        f"{auditor_model or 'none'}|{1 if chain_verified else 0}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_certificate_data(
    audit: VeritasAuditLog,
    chain_verified: bool,
) -> ComplianceCertificateResponse:
    """Constructs the canonical compliance certificate schema from an audit record."""
    verified_quotes: list[VerifiedQuoteClaim] = []
    for c in audit.claim_audits or []:
        verified_quotes.append(
            VerifiedQuoteClaim(
                claim_id=str(c.get("claim_id") or "CLM"),
                verbatim_quote=c.get("verbatim_quote"),
                matched_doc_id=c.get("matched_doc_id"),
                quote_verified=bool(c.get("quote_verified")),
                numeric_mismatch=bool(c.get("numeric_mismatch")),
                fy_mismatch=bool(c.get("fy_mismatch")),
                cross_lab_supported=bool(c.get("cross_lab_supported")),
            )
        )

    seal = compute_certificate_seal(
        audit_id=audit.audit_id,
        record_hash=audit.record_hash,
        prev_hash=audit.prev_hash,
        verdict=audit.verdict,
        policy_applied=audit.policy_applied,
        primary_model=audit.primary_model,
        auditor_model=audit.auditor_model,
        chain_verified=chain_verified,
    )

    issued_at = audit.created_at.isoformat() if hasattr(audit.created_at, "isoformat") else str(audit.created_at)

    return ComplianceCertificateResponse(
        audit_id=audit.audit_id,
        issued_at_utc=issued_at,
        verdict=audit.verdict.upper(),
        policy_applied=audit.policy_applied.lower(),
        safe_to_publish=(audit.verdict.upper() == "APPROVE"),
        primary_model=audit.primary_model,
        auditor_model=audit.auditor_model,
        prev_hash=audit.prev_hash,
        record_hash=audit.record_hash,
        chain_verified=chain_verified,
        latency_ms=audit.latency_ms or 0,
        estimated_cost_usd=audit.estimated_cost_usd,
        verified_quotes=verified_quotes,
        certificate_seal_sha256=seal,
        issuer="MNB Veritas Forensic Evidence Engine v1.4",
    )


def render_certificate_pdf(cert: ComplianceCertificateResponse) -> bytes:
    """
    Renders a formatted printable PDF certificate using PyMuPDF (fitz).
    Contains certificate headers, verdict badges, cryptographic SHA-256 hashes,
    model provenance, and verified verbatim quotes.
    """
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)  # Standard A4

        # 1. Header Banner
        page.draw_rect(fitz.Rect(0, 0, 595, 75), fill=(0.06, 0.09, 0.13))
        page.insert_text(
            fitz.Point(36, 36),
            "MNB VERITAS COMPLIANCE CERTIFICATE",
            fontsize=15,
            color=(0.95, 0.96, 0.98),
        )
        page.insert_text(
            fitz.Point(36, 56),
            "Forensic Evidence Verification & Non-Repudiation Audit Seal",
            fontsize=9,
            color=(0.60, 0.65, 0.72),
        )

        # 2. Verdict Banner
        is_approved = cert.verdict == "APPROVE"
        is_qualify = cert.verdict == "QUALIFY"
        if is_approved:
            v_fill = (0.05, 0.28, 0.15)
            v_border = (0.16, 0.65, 0.35)
            v_text = "VERDICT: APPROVE · SAFE TO PUBLISH"
        elif is_qualify:
            v_fill = (0.32, 0.22, 0.05)
            v_border = (0.75, 0.52, 0.10)
            v_text = "VERDICT: QUALIFY · CONDITIONAL PUBLICATION"
        else:
            v_fill = (0.35, 0.08, 0.10)
            v_border = (0.80, 0.20, 0.24)
            v_text = f"VERDICT: {cert.verdict} · DO NOT PUBLISH (VETOED)"

        page.draw_rect(fitz.Rect(36, 90, 559, 130), fill=v_fill, color=v_border, width=1)
        page.insert_text(fitz.Point(50, 115), v_text, fontsize=12, color=(1, 1, 1))

        # 3. Governance & Pipeline Details (2-Column Grid)
        y = 150
        page.draw_rect(fitz.Rect(36, y, 559, y + 130), fill=(0.97, 0.98, 0.99), color=(0.85, 0.88, 0.92), width=1)

        # Left Column
        page.insert_text(fitz.Point(50, y + 25), "Audit ID:", fontsize=9, color=(0.4, 0.45, 0.5))
        page.insert_text(fitz.Point(140, y + 25), cert.audit_id, fontsize=9, color=(0.1, 0.1, 0.1))

        page.insert_text(fitz.Point(50, y + 50), "Policy Mode:", fontsize=9, color=(0.4, 0.45, 0.5))
        page.insert_text(fitz.Point(140, y + 50), cert.policy_applied.upper(), fontsize=9, color=(0.1, 0.1, 0.1))

        page.insert_text(fitz.Point(50, y + 75), "Primary Model:", fontsize=9, color=(0.4, 0.45, 0.5))
        page.insert_text(fitz.Point(140, y + 75), cert.primary_model, fontsize=9, color=(0.1, 0.1, 0.1))

        page.insert_text(fitz.Point(50, y + 100), "Cross-Lab Auditor:", fontsize=9, color=(0.4, 0.45, 0.5))
        page.insert_text(fitz.Point(140, y + 100), cert.auditor_model or "None (Single Lab Mode)", fontsize=9, color=(0.1, 0.1, 0.1))

        # Right Column
        page.insert_text(fitz.Point(310, y + 25), "Issued At (UTC):", fontsize=9, color=(0.4, 0.45, 0.5))
        page.insert_text(fitz.Point(400, y + 25), cert.issued_at_utc[:19].replace("T", " "), fontsize=9, color=(0.1, 0.1, 0.1))

        page.insert_text(fitz.Point(310, y + 50), "Chain Linkage:", fontsize=9, color=(0.4, 0.45, 0.5))
        chain_label = "VERIFIED INTACT" if cert.chain_verified else "TAMPER DETECTED"
        chain_color = (0.1, 0.5, 0.2) if cert.chain_verified else (0.8, 0.1, 0.1)
        page.insert_text(fitz.Point(400, y + 50), chain_label, fontsize=9, color=chain_color)

        page.insert_text(fitz.Point(310, y + 75), "Execution Latency:", fontsize=9, color=(0.4, 0.45, 0.5))
        page.insert_text(fitz.Point(400, y + 75), f"{cert.latency_ms} ms", fontsize=9, color=(0.1, 0.1, 0.1))

        page.insert_text(fitz.Point(310, y + 100), "Telemetry Cost:", fontsize=9, color=(0.4, 0.45, 0.5))
        page.insert_text(fitz.Point(400, y + 100), f"${cert.estimated_cost_usd or 0.0:.4f} USD", fontsize=9, color=(0.1, 0.1, 0.1))

        # 4. Cryptographic Proof Hashes
        y_crypto = y + 145
        page.draw_rect(fitz.Rect(36, y_crypto, 559, y_crypto + 95), fill=(0.10, 0.12, 0.16), color=(0.20, 0.24, 0.30), width=1)
        page.insert_text(fitz.Point(50, y_crypto + 20), "CRYPTOGRAPHIC PROOF & NON-REPUDIATION HASHES", fontsize=9, color=(0.40, 0.75, 0.95))

        page.insert_text(fitz.Point(50, y_crypto + 42), "Record SHA-256:", fontsize=8, color=(0.6, 0.65, 0.7))
        page.insert_text(fitz.Point(145, y_crypto + 42), cert.record_hash or "UNHASHED_LEGACY", fontsize=8, color=(0.85, 0.90, 0.95))

        page.insert_text(fitz.Point(50, y_crypto + 62), "Predecessor Hash:", fontsize=8, color=(0.6, 0.65, 0.7))
        page.insert_text(fitz.Point(145, y_crypto + 62), cert.prev_hash or "GENESIS", fontsize=8, color=(0.85, 0.90, 0.95))

        page.insert_text(fitz.Point(50, y_crypto + 82), "Certificate Seal:", fontsize=8, color=(0.6, 0.65, 0.7))
        page.insert_text(fitz.Point(145, y_crypto + 82), cert.certificate_seal_sha256, fontsize=8, color=(0.20, 0.85, 0.55))

        # 5. Verified Claims & Verbatim Evidence Section
        y_claims = y_crypto + 115
        page.insert_text(fitz.Point(36, y_claims), "VERIFIED CLAIM EVIDENCE & GROUNDING AUDIT", fontsize=11, color=(0.1, 0.15, 0.25))

        cur_y = y_claims + 15
        if cert.verified_quotes:
            for idx, q in enumerate(cert.verified_quotes[:4]):  # Format up to 4 primary claims
                box_height = 65
                page.draw_rect(fitz.Rect(36, cur_y, 559, cur_y + box_height), fill=(0.98, 0.98, 0.99), color=(0.85, 0.88, 0.92), width=1)
                status_str = f"Quote: {'PASSED' if q.quote_verified else 'FAILED'}  |  Numeric: {'OK' if not q.numeric_mismatch else 'MISMATCH'}  |  FY: {'OK' if not q.fy_mismatch else 'MISMATCH'}  |  Cross-Lab: {'OK' if q.cross_lab_supported else 'REJECTED'}"
                page.insert_text(fitz.Point(46, cur_y + 18), f"Claim [{q.claim_id}] · Source [{q.matched_doc_id or 'None'}]", fontsize=8, color=(0.2, 0.25, 0.3))
                page.insert_text(fitz.Point(260, cur_y + 18), status_str, fontsize=7, color=(0.1, 0.4, 0.2) if q.quote_verified else (0.7, 0.2, 0.2))

                quote_snippet = q.verbatim_quote or "No verbatim quote grounded from source text."
                if len(quote_snippet) > 170:
                    quote_snippet = quote_snippet[:167] + "..."
                page.insert_textbox(fitz.Rect(46, cur_y + 24, 545, cur_y + 60), f'"{quote_snippet}"', fontsize=8, color=(0.25, 0.25, 0.25))
                cur_y += box_height + 8
        else:
            page.insert_text(fitz.Point(36, cur_y + 20), "No factual claims extracted for this verification query.", fontsize=9, color=(0.5, 0.5, 0.5))

        # 6. Footer
        page.draw_line(fitz.Point(36, 805), fitz.Point(559, 805), color=(0.8, 0.85, 0.9), width=1)
        page.insert_text(
            fitz.Point(36, 820),
            "MNB Veritas v1.4 Forensic Engine · Zero-PII Telemetry · Tamper-Evident SHA-256 Linkage",
            fontsize=8,
            color=(0.55, 0.60, 0.65),
        )
        page.insert_text(
            fitz.Point(480, 820),
            "Page 1 of 1",
            fontsize=8,
            color=(0.55, 0.60, 0.65),
        )

        buf = doc.tobytes()
        return buf
    finally:
        doc.close()
