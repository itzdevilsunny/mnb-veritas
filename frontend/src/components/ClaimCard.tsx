"use client";

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type { ClaimAudit } from "@/types/veritas";
import { ClaimProvenanceDAG } from "./ClaimProvenanceDAG";

export function ClaimCard({
  item,
  sourceDocText,
}: {
  item: ClaimAudit;
  sourceDocText?: string;
}) {
  const [showDAG, setShowDAG] = useState(false);
  const passed =
    item.is_factual &&
    item.quote_verified &&
    !item.numeric_mismatch &&
    !item.fy_mismatch &&
    item.cross_lab_supported;

  const tag = !item.is_factual
    ? "SYNTHESIS / OPINION"
    : item.included_in_answer || passed
    ? "VERIFIED FACT"
    : "VETOED CLAIM";

  const tagCls = !item.is_factual
    ? "border-[#27272A] bg-[#18181B] text-zinc-400"
    : item.included_in_answer || passed
    ? "border-emerald-800/60 bg-emerald-950/40 text-emerald-300"
    : "border-rose-800/60 bg-rose-950/40 text-rose-300";

  // Forensic verbatim quote highlighting
  const renderSourceQuoteHighlight = () => {
    if (!item.verbatim_quote) return null;

    return (
      <div className="space-y-1.5 pt-1">
        <div className="flex items-center justify-between text-[10px] font-mono text-zinc-400">
          <span className="flex items-center gap-1 font-semibold uppercase tracking-wider text-zinc-400">
            <FileText className="h-3 w-3 text-emerald-400" />
            Cited Verbatim Evidence Chunk
            {item.matched_doc_id ? ` [${item.matched_doc_id}]` : ""}
          </span>
          {item.quote_verified ? (
            <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold">
              <CheckCircle2 className="h-3 w-3" />
              100% Exact Substring Proof
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-rose-400 font-semibold">
              <XCircle className="h-3 w-3" />
              Paraphrase / Substring Missing
            </span>
          )}
        </div>

        <blockquote
          className={`rounded-md border-l-2 p-3 font-sans text-xs leading-relaxed ${
            item.quote_verified
              ? "border-emerald-500 bg-emerald-950/20 text-zinc-200"
              : "border-rose-500 bg-rose-950/20 text-rose-200"
          }`}
        >
          <span className="text-zinc-500 font-mono text-[11px] select-none mr-1">“</span>
          <mark
            className={`rounded px-1 py-0.5 font-medium ${
              item.quote_verified
                ? "bg-emerald-900/40 text-emerald-100 border-b border-emerald-400"
                : "bg-rose-900/40 text-rose-100 border-b border-rose-400"
            }`}
          >
            {item.verbatim_quote}
          </mark>
          <span className="text-zinc-500 font-mono text-[11px] select-none ml-1">”</span>
        </blockquote>
      </div>
    );
  };

  return (
    <div className="space-y-3 rounded-lg border border-[#27272A] bg-[#111114] p-4 text-xs font-sans transition-colors hover:border-zinc-700">
      {/* Claim Header */}
      <div className="flex items-start justify-between gap-3 border-b border-[#27272A] pb-2.5">
        <div className="space-y-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 font-mono text-[11px] text-zinc-400">
            <span className="font-semibold text-zinc-200">{item.claim_id}</span>
            {item.matched_doc_id && (
              <span className="text-zinc-400">
                · DOC: <span className="text-zinc-300 font-semibold">{item.matched_doc_id}</span>
              </span>
            )}
            {item.page_number != null && (
              <span className="text-zinc-500">· Page {item.page_number}</span>
            )}
          </div>
          <p className="text-sm font-medium text-zinc-100 leading-snug">{item.claim_text}</p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setShowDAG(!showDAG)}
            className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-2 py-1 text-[10px] font-mono text-zinc-300 hover:text-zinc-100 hover:border-zinc-600 transition"
          >
            <ShieldCheck className="h-3 w-3 text-cyan-400" />
            <span>DAG</span>
            {showDAG ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
          <span className={`rounded border px-2 py-0.5 font-mono text-[10px] font-semibold tracking-wider ${tagCls}`}>
            {tag}
          </span>
        </div>
      </div>

      {/* Deterministic Verification Check Chips */}
      {item.is_factual && (
        <div className="flex flex-wrap gap-1.5 font-mono text-[10px]">
          {/* Substring Quote Check */}
          <span
            className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 ${
              item.quote_verified
                ? "border-emerald-900/60 bg-emerald-950/30 text-emerald-300"
                : "border-rose-900/60 bg-rose-950/30 text-rose-300"
            }`}
          >
            {item.quote_verified ? (
              <CheckCircle2 className="h-2.5 w-2.5 text-emerald-400" />
            ) : (
              <XCircle className="h-2.5 w-2.5 text-rose-400" />
            )}
            <span>Quote: {item.quote_verified ? "Exact Substring" : "Missing / Paraphrase"}</span>
          </span>

          {/* Scale Check */}
          <span
            className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 ${
              !item.numeric_mismatch
                ? "border-emerald-900/60 bg-emerald-950/30 text-emerald-300"
                : "border-rose-900/60 bg-rose-950/30 text-rose-300"
            }`}
          >
            {!item.numeric_mismatch ? (
              <CheckCircle2 className="h-2.5 w-2.5 text-emerald-400" />
            ) : (
              <XCircle className="h-2.5 w-2.5 text-rose-400" />
            )}
            <span>Scale/Crore: {!item.numeric_mismatch ? "Reconciled" : "Scale Contradiction"}</span>
          </span>

          {/* Financial Year Check */}
          <span
            className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 ${
              !item.fy_mismatch
                ? "border-emerald-900/60 bg-emerald-950/30 text-emerald-300"
                : "border-rose-900/60 bg-rose-950/30 text-rose-300"
            }`}
          >
            {!item.fy_mismatch ? (
              <CheckCircle2 className="h-2.5 w-2.5 text-emerald-400" />
            ) : (
              <XCircle className="h-2.5 w-2.5 text-rose-400" />
            )}
            <span>FY Window: {!item.fy_mismatch ? "Matched" : "Boundary Mismatch"}</span>
          </span>

          {/* Cross-Lab Entailment */}
          <span
            className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 ${
              item.cross_lab_supported
                ? "border-emerald-900/60 bg-emerald-950/30 text-emerald-300"
                : "border-rose-900/60 bg-rose-950/30 text-rose-300"
            }`}
          >
            {item.cross_lab_supported ? (
              <CheckCircle2 className="h-2.5 w-2.5 text-emerald-400" />
            ) : (
              <XCircle className="h-2.5 w-2.5 text-rose-400" />
            )}
            <span>Cross-Lab: {item.cross_lab_supported ? "Entailed" : "Not Entailed"}</span>
          </span>

          {/* Temporal Validity */}
          <span
            className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 ${
              !item.source_expired
                ? "border-emerald-900/60 bg-emerald-950/30 text-emerald-300"
                : "border-rose-900/60 bg-rose-950/30 text-rose-300"
            }`}
          >
            {!item.source_expired ? (
              <CheckCircle2 className="h-2.5 w-2.5 text-emerald-400" />
            ) : (
              <AlertTriangle className="h-2.5 w-2.5 text-rose-400" />
            )}
            <span>Temporal: {!item.source_expired ? "In-Bound" : "Expired Gazette"}</span>
          </span>
        </div>
      )}

      {/* Collapsible Claim Provenance DAG */}
      {showDAG && (
        <div className="pt-1">
          <ClaimProvenanceDAG
            claim={item}
            overallVerdict={passed ? "APPROVE" : "ABSTAIN"}
            auditorModel={item.cross_lab_supported ? "Entailed" : null}
            sourceAuthorityTier="regulatory"
          />
        </div>
      )}

      {/* Verbatim Substring Highlight */}
      {renderSourceQuoteHighlight()}

      {/* Discrepancy Warnings */}
      {item.reasons.length > 0 && (
        <div className="rounded border border-rose-900/40 bg-rose-950/20 p-2 text-rose-300 font-mono text-[11px] space-y-1">
          <div className="font-semibold uppercase tracking-wider text-rose-400 flex items-center gap-1 text-[10px]">
            <AlertTriangle className="h-3 w-3" />
            Forensic Discrepancy Findings
          </div>
          <ul className="list-disc pl-4 space-y-0.5 font-sans">
            {item.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
