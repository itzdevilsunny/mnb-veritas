"use client";

import { useState } from "react";
import type { ClaimAudit } from "@/types/veritas";
import { ClaimProvenanceDAG } from "./ClaimProvenanceDAG";
import { Chip } from "./ui";

export function ClaimCard({ item }: { item: ClaimAudit }) {
  const [showDAG, setShowDAG] = useState(false);
  const passed =
    item.is_factual && item.quote_verified && !item.numeric_mismatch && !item.fy_mismatch && item.cross_lab_supported;
  const tag = !item.is_factual ? "OPINION" : item.included_in_answer ? "IN ANSWER" : passed ? "VERIFIED" : "REJECTED";
  const tagCls = !item.is_factual
    ? "border-zinc-700 text-zinc-400"
    : item.included_in_answer || passed
      ? "border-emerald-700/60 bg-emerald-950/60 text-emerald-300"
      : "border-rose-700/60 bg-rose-950/60 text-rose-300";

  return (
    <div className="space-y-2.5 rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
            <span className="font-mono uppercase">{item.claim_id}</span>
            {item.matched_doc_id && <span className="font-mono text-zinc-300">· {item.matched_doc_id}</span>}
          </div>
          <p className="text-sm font-medium text-zinc-100">{item.claim_text}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowDAG(!showDAG)}
            className="rounded border border-zinc-700 bg-zinc-800/80 px-2 py-0.5 text-[10px] font-mono text-zinc-300 hover:bg-zinc-700 transition"
          >
            {showDAG ? "DAG ▲" : "DAG ▼"}
          </button>
          <span className={`shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${tagCls}`}>{tag}</span>
        </div>
      </div>

      {item.is_factual && (
        <div className="flex flex-wrap gap-1.5">
          <Chip ok={item.quote_verified}>quote: {item.quote_verified ? "exact match" : "not found"}</Chip>
          <Chip ok={!item.numeric_mismatch}>numbers/units: {item.numeric_mismatch ? "mismatch" : "ok"}</Chip>
          <Chip ok={!item.fy_mismatch}>financial year: {item.fy_mismatch ? "mismatch" : "ok"}</Chip>
          <Chip ok={item.cross_lab_status === "entailed" || item.cross_lab_supported}>cross-lab: {item.cross_lab_status ?? (item.cross_lab_supported ? "entailed" : "not entailed")}</Chip>
          <Chip ok={item.source_status === "valid" || !item.source_expired}>source: {(item.source_status ?? (item.source_expired ? "expired" : "valid")).replace("_", " ")}</Chip>
        </div>
      )}

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

      {item.verbatim_quote && (
        <blockquote className="rounded-lg border-l-2 border-sky-500 bg-zinc-950/80 px-3 py-2 text-xs text-zinc-300">
          “{item.verbatim_quote}”
        </blockquote>
      )}

      {item.reasons.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-4 text-xs text-rose-300/90">
          {item.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
