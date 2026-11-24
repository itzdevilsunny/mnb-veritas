"use client";

import type { ClaimAuditItem, Verdict } from "@/types/veritas";

interface ClaimProvenanceDAGProps {
  claim: ClaimAuditItem;
  overallVerdict: Verdict;
  auditorModel?: string | null;
  policy?: string;
  sourceAuthorityTier?: string;
}

export function ClaimProvenanceDAG({
  claim,
  overallVerdict,
  auditorModel,
  policy = "strict",
  sourceAuthorityTier = "regulatory",
}: ClaimProvenanceDAGProps) {
  const codeGatePassed = claim.quote_verified && !claim.numeric_mismatch && !claim.fy_mismatch;
  const sourcePassed = !claim.source_expired && !!claim.matched_doc_id;
  const crossLabPassed = claim.cross_lab_supported;
  const isStrict = policy.toLowerCase() === "strict";

  return (
    <div className="rounded-lg border border-[#27272A] bg-[#111114] p-3 space-y-2 font-sans">
      <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 pb-1.5 border-b border-[#27272A]">
        <span className="flex items-center gap-1.5 font-semibold text-zinc-300">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-cyan-400"></span>
          PROVENANCE GRAPH · {claim.claim_id}
        </span>
        <span className="uppercase text-[10px] text-zinc-500">Pipeline Flow: S1 → S2 → S3 → S4 → S5</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-2 items-stretch text-xs font-mono">
        {/* Node 1: Truth Source Chunk */}
        <div
          className={`rounded-lg border p-2.5 flex flex-col justify-between ${
            sourcePassed
              ? "border-emerald-800/60 bg-emerald-950/20 text-zinc-200"
              : "border-rose-800/60 bg-rose-950/20 text-zinc-200"
          }`}
        >
          <div>
            <div className="text-[10px] font-semibold tracking-wider uppercase text-zinc-400 flex items-center justify-between">
              <span>1. SOURCE</span>
              <span className="text-[9px] px-1 py-0.2 rounded bg-zinc-800/80 text-zinc-300">
                {sourceAuthorityTier.toUpperCase()}
              </span>
            </div>
            <p className="mt-1 font-semibold truncate text-[11px] text-zinc-100">
              {claim.matched_doc_id || "MISSING SOURCE"}
            </p>
          </div>
          <div className="mt-2 text-[10px] flex items-center gap-1">
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                sourcePassed ? "bg-emerald-400" : "bg-rose-400"
              }`}
            />
            <span className={sourcePassed ? "text-emerald-300" : "text-rose-300"}>
              {sourcePassed ? "Valid Window" : "Expired / Missing"}
            </span>
          </div>
        </div>

        {/* Node 2: Atomic Claim */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-2.5 flex flex-col justify-between text-zinc-200">
          <div>
            <div className="text-[10px] font-semibold tracking-wider uppercase text-zinc-400 flex items-center justify-between">
              <span>2. CLAIM</span>
              <span className="text-[9px] px-1 py-0.2 rounded bg-cyan-950/80 text-cyan-300">
                {claim.is_factual ? "FACTUAL" : "GENERAL"}
              </span>
            </div>
            <p className="mt-1 line-clamp-2 text-[10px] text-zinc-300 italic">
              &quot;{claim.claim_text}&quot;
            </p>
          </div>
          <div className="mt-2 text-[10px] text-zinc-500 font-mono">ID: {claim.claim_id}</div>
        </div>

        {/* Node 3: Deterministic Code Gate */}
        <div
          className={`rounded-lg border p-2.5 flex flex-col justify-between ${
            codeGatePassed
              ? "border-emerald-800/60 bg-emerald-950/20 text-zinc-200"
              : "border-rose-800/60 bg-rose-950/20 text-zinc-200"
          }`}
        >
          <div>
            <div className="text-[10px] font-semibold tracking-wider uppercase text-zinc-400">
              3. CODE VETO GATE
            </div>
            <div className="mt-1 space-y-0.5 text-[10px]">
              <div className="flex justify-between">
                <span className="text-zinc-400">Quote:</span>
                <span className={claim.quote_verified ? "text-emerald-300" : "text-rose-400"}>
                  {claim.quote_verified ? "MATCH" : "VETO"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Numbers:</span>
                <span className={!claim.numeric_mismatch ? "text-emerald-300" : "text-rose-400"}>
                  {!claim.numeric_mismatch ? "CONCORD" : "100x MISMATCH"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">FY Term:</span>
                <span className={!claim.fy_mismatch ? "text-emerald-300" : "text-rose-400"}>
                  {!claim.fy_mismatch ? "ALIGNED" : "MISMATCH"}
                </span>
              </div>
            </div>
          </div>
          <div className="mt-1.5 text-[10px] font-semibold flex items-center gap-1">
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                codeGatePassed ? "bg-emerald-400" : "bg-rose-400"
              }`}
            />
            <span className={codeGatePassed ? "text-emerald-300" : "text-rose-300"}>
              {codeGatePassed ? "Gate Cleared" : "Deterministic Veto"}
            </span>
          </div>
        </div>

        {/* Node 4: Cross-Lab Auditor */}
        <div
          className={`rounded-lg border p-2.5 flex flex-col justify-between ${
            crossLabPassed
              ? "border-emerald-800/60 bg-emerald-950/20 text-zinc-200"
              : isStrict
              ? "border-rose-800/60 bg-rose-950/20 text-zinc-200"
              : "border-amber-800/60 bg-amber-950/20 text-zinc-200"
          }`}
        >
          <div>
            <div className="text-[10px] font-semibold tracking-wider uppercase text-zinc-400">
              4. CROSS-LAB
            </div>
            <p className="mt-1 font-semibold truncate text-[11px] text-zinc-100">
              {auditorModel ? auditorModel.split(":")[0].toUpperCase() : "SINGLE LAB"}
            </p>
            <p className="text-[10px] text-zinc-400 truncate">{auditorModel || "No Auditor"}</p>
          </div>
          <div className="mt-2 text-[10px] flex items-center gap-1">
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                crossLabPassed
                  ? "bg-emerald-400"
                  : isStrict
                  ? "bg-rose-400"
                  : "bg-amber-400"
              }`}
            />
            <span
              className={
                crossLabPassed
                  ? "text-emerald-300"
                  : isStrict
                  ? "text-rose-300"
                  : "text-amber-300"
              }
            >
              {crossLabPassed ? "Entailed" : isStrict ? "Veto (Strict)" : "Single Lab"}
            </span>
          </div>
        </div>

        {/* Node 5: Final Verdict */}
        <div
          className={`rounded-lg border p-2.5 flex flex-col justify-between ${
            overallVerdict === "APPROVE"
              ? "border-emerald-500/80 bg-emerald-950/30 text-emerald-200"
              : overallVerdict === "QUALIFY"
              ? "border-amber-500/80 bg-amber-950/30 text-amber-200"
              : "border-rose-500/80 bg-rose-950/30 text-rose-200"
          }`}
        >
          <div>
            <div className="text-[10px] font-semibold tracking-wider uppercase text-zinc-400">
              5. DECISION
            </div>
            <div className="mt-1 text-sm font-bold tracking-wide">
              {overallVerdict}
            </div>
          </div>
          <div className="mt-2 text-[10px] font-mono">
            {overallVerdict === "APPROVE" ? "SAFE TO PUBLISH" : "NO PUBLISH"}
          </div>
        </div>
      </div>
    </div>
  );
}
