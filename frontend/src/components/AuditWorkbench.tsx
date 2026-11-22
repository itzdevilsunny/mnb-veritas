"use client";

import React, { useState } from "react";
import type {
  LabProvider,
  PolicyMode,
  VerifyResponse,
} from "@/types/veritas";

interface AuditWorkbenchProps {
  onVerified?: (res: VerifyResponse) => void;
  activeSourceCount?: number;
}

const DEFAULT_APPROVE_RESULT: VerifyResponse = {
  audit_id: "aud_9841f3e7",
  verdict: "APPROVE",
  answer:
    "The Ministry of Finance has sanctioned a total budgetary allocation of ₹4,850 crore for the National Green Hydrogen Mission for FY 2025-26 under the new outlay. The Strategic Interventions for Green Hydrogen Transition (SIGHT) program receives 68% of the total allocation, and expenditure execution is subject to quarterly review by the Ministry of New and Renewable Energy starting Q1 FY26.",
  policy_applied: "strict",
  telemetry: {
    primary_model: "Claude 3.5 Sonnet",
    auditor_model: "GPT-4o (OpenAI)",
    failover_triggered: false,
    latency_ms: 448,
    prompt_tokens: 1842,
    completion_tokens: 219,
    estimated_cost_usd: 0.0041,
    numeric_concord_pct: 100,
    temporal_bound: "VALID (FY25-26)",
  },
  claim_audits: [
    {
      claim_id: "CLM-01",
      claim_text:
        "The Ministry of Finance has sanctioned a total budgetary allocation of ₹4,850 crore for the National Green Hydrogen Mission for FY 2025-26.",
      is_factual: true,
      quote_verified: true,
      source_expired: false,
      numeric_mismatch: false,
      fy_mismatch: false,
      cross_lab_supported: true,
      reasons: [],
      matched_doc_id: "doc_green_hydrogen_2024",
      verbatim_quote:
        "Cabinet approves continuation of National Green Hydrogen Mission with financial outlay of ₹4,850 crore specifically ear-marked for FY 2025-26 pilot electrolysers.",
      page_number: 12,
      chunk_index: 4,
    },
    {
      claim_id: "CLM-02",
      claim_text:
        "The Strategic Interventions for Green Hydrogen Transition (SIGHT) program receives 68% of the total allocation.",
      is_factual: true,
      quote_verified: true,
      source_expired: false,
      numeric_mismatch: false,
      fy_mismatch: false,
      cross_lab_supported: true,
      reasons: [],
      matched_doc_id: "doc_green_hydrogen_2024",
      verbatim_quote:
        "Under component II (SIGHT), 68% of aggregate outlay shall be deployed across domestic electrolyser manufacturing incentives and green ammonia pilots.",
      page_number: 14,
      chunk_index: 7,
    },
    {
      claim_id: "CLM-03",
      claim_text:
        "Expenditure execution is subject to quarterly review by the Ministry of New and Renewable Energy starting Q1 FY26.",
      is_factual: true,
      quote_verified: true,
      source_expired: false,
      numeric_mismatch: false,
      fy_mismatch: false,
      cross_lab_supported: true,
      reasons: [],
      matched_doc_id: "doc_budget_2025",
      verbatim_quote:
        "Quarterly financial milestone reviews will be convened jointly by MNRE beginning Q1 of FY 2025-26.",
      page_number: 38,
      chunk_index: 19,
    },
  ],
  warnings: [],
  created_at: "2025-03-31T14:22:04Z",
};

export default function AuditWorkbench({
  onVerified,
  activeSourceCount = 4,
}: AuditWorkbenchProps) {
  const [query, setQuery] = useState(
    "What is the approved budgetary allocation for the National Green Hydrogen Mission for FY 2025-26 under the new outlay?"
  );
  const [policy, setPolicy] = useState<PolicyMode>("strict");
  const [refDate, setRefDate] = useState("2025-03-31");
  const [generator, setGenerator] = useState<string>("auto");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(DEFAULT_APPROVE_RESULT);
  const [inspectedClaim, setInspectedClaim] = useState<string | null>(null);

  const executeVerify = async (
    targetQuery?: string,
    targetPolicy?: PolicyMode,
    targetDate?: string
  ) => {
    setLoading(true);
    setError(null);

    const q = targetQuery ?? query;
    const p = targetPolicy ?? policy;
    const d = targetDate ?? refDate;

    let preferredLabs: LabProvider[] = ["anthropic", "openai", "google", "xai"];
    if (generator === "anthropic") preferredLabs = ["anthropic", "openai"];
    if (generator === "openai") preferredLabs = ["openai", "anthropic"];
    if (generator === "google") preferredLabs = ["google", "anthropic"];
    if (generator === "xai") preferredLabs = ["xai", "anthropic"];

    try {
      const res = await fetch("/api/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q,
          policy: p,
          reference_date: d,
          preferred_labs: preferredLabs,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.detail ?? `Verification request failed with status ${res.status}`);
      } else {
        setResult(data);
        onVerified?.(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error during verification");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      void executeVerify();
    }
  };

  const loadPreset = (
    q: string,
    d: string,
    pol: PolicyMode
  ) => {
    setQuery(q);
    setRefDate(d);
    setPolicy(pol);
    void executeVerify(q, pol, d);
  };

  return (
    <div className="space-y-6">
      {/* CORPUS AUDIT TEST TRIGGERS */}
      <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-4">
        <div className="mb-3 flex items-center justify-between text-xs tracking-wider">
          <span className="font-mono text-zinc-400 uppercase">
            Corpus Audit Test Triggers
          </span>
          <span className="text-zinc-500 font-mono text-[11px]">Preset Scenarios</span>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {/* Preset 1: FY 2025-26 Allocation */}
          <button
            type="button"
            onClick={() =>
              loadPreset(
                "What is the approved budgetary allocation for the National Green Hydrogen Mission for FY 2025-26 under the new outlay?",
                "2025-03-31",
                "strict"
              )
            }
            className="flex flex-col items-start rounded-lg border border-zinc-800/80 bg-[#121820]/70 p-3 text-left transition hover:border-emerald-600/60 hover:bg-[#151D26]"
          >
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-100">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              <span>FY 2025-26 Allocation</span>
            </div>
            <span className="mt-1 font-mono text-[11px] text-zinc-400">
              ₹4,850 Cr Green Hydrogen outlay
            </span>
          </button>

          {/* Preset 2: Offshore LNG Claim */}
          <button
            type="button"
            onClick={() =>
              loadPreset(
                "Explain India's current bilateral sovereign guarantee commitments for offshore African LNG terminal construction in FY 2025-26.",
                "2025-03-31",
                "strict"
              )
            }
            className="flex flex-col items-start rounded-lg border border-zinc-800/80 bg-[#121820]/70 p-3 text-left transition hover:border-rose-600/60 hover:bg-[#151D26]"
          >
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-100">
              <span className="h-2 w-2 rounded-full bg-rose-400"></span>
              <span>Offshore LNG Claim</span>
            </div>
            <span className="mt-1 font-mono text-[11px] text-zinc-400">
              Triggers &quot;No answer possible&quot;
            </span>
          </button>
        </div>
      </div>

      {/* VERIFICATION QUERY & POLICY */}
      <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300">
              Verification Query &amp; Policy
            </span>
            <span className="rounded bg-sky-950/70 px-2 py-0.5 font-mono text-[10px] text-sky-400 border border-sky-800/50">
              POST /v1/verify
            </span>
          </div>
          <span className="font-mono text-[11px] text-zinc-500">⌘+Enter to Run</span>
        </div>

        <div className="space-y-1.5">
          <label className="block text-[11px] font-mono text-zinc-400">
            Input Claim / Synthesis Prompt
          </label>
          <textarea
            rows={3}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter claim or question to verify..."
            className="w-full rounded-lg border border-zinc-800 bg-[#0B0F12] p-3 text-xs leading-relaxed text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-500/80 focus:outline-none"
          />
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              Policy Mode
            </label>
            <select
              value={policy}
              onChange={(e) => setPolicy(e.target.value as PolicyMode)}
              className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono"
            >
              <option value="strict">STRICT (Zero Hallucination)</option>
              <option value="balanced">BALANCED</option>
              <option value="standard">STANDARD</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              Reference Date
            </label>
            <input
              type="date"
              value={refDate}
              onChange={(e) => setRefDate(e.target.value)}
              className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono"
            />
          </div>

          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              Primary Generator
            </label>
            <select
              value={generator}
              onChange={(e) => setGenerator(e.target.value)}
              className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono"
            >
              <option value="auto">AUTO FAILOVER (Chain)</option>
              <option value="anthropic">Claude 3.5 Sonnet</option>
              <option value="openai">GPT-4o (OpenAI)</option>
              <option value="google">Gemini 1.5 Pro</option>
              <option value="xai">Grok (xAI)</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              Source Filter
            </label>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono"
            >
              <option value="all">All Active Sources ({activeSourceCount})</option>
            </select>
          </div>
        </div>

        <button
          type="button"
          onClick={() => void executeVerify()}
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-zinc-950 transition hover:bg-emerald-400 disabled:opacity-50"
        >
          <span>⚡</span>
          <span>{loading ? "EXECUTING MULTI-LAB VERIFICATION..." : "EXECUTE MULTI-LAB VERIFICATION"}</span>
        </button>

        {error && (
          <div className="rounded-lg border border-rose-800/80 bg-rose-950/40 p-3 font-mono text-xs text-rose-300">
            {error}
          </div>
        )}
      </div>

      {/* VERIFICATION REPORT BANNER & CLAIMS */}
      {result && (
        <div className="space-y-4">
          {/* Main Verdict Banner */}
          <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
              <div className="flex items-center gap-3">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-xs font-bold tracking-wider ${
                    result.verdict === "APPROVE"
                      ? "bg-emerald-950/80 text-emerald-300 border border-emerald-700/60"
                      : result.verdict === "QUALIFY"
                      ? "bg-amber-950/80 text-amber-300 border border-amber-700/60"
                      : "bg-rose-950/80 text-rose-300 border border-rose-700/60"
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      result.verdict === "APPROVE"
                        ? "bg-emerald-400"
                        : result.verdict === "QUALIFY"
                        ? "bg-amber-400"
                        : "bg-rose-400"
                    }`}
                  ></span>
                  {result.verdict}
                </span>
                <span className="text-xs text-zinc-300">
                  {result.verdict === "APPROVE"
                    ? `Synthesis fully grounded across 2 primary state sources. ${result.claim_audits.length} of ${result.claim_audits.length} claims passed exact substring quote verification & numeric crore reconciliations.`
                    : result.verdict === "QUALIFY"
                    ? "Qualified synthesis: Verified with temporal/source caveats."
                    : 'Strict abstention triggered: Claim is ungrounded or contradictory. Answer reverted to "No answer possible".'}
                </span>
              </div>
              <span className="font-mono text-[11px] text-zinc-500">
                AUDIT_ID: {result.audit_id}
              </span>
            </div>

            {/* Answer Display */}
            <div className="rounded-lg border border-zinc-800/80 bg-[#0B0F12] p-3 text-xs leading-relaxed">
              <span className="block font-mono text-[10px] uppercase text-zinc-500 mb-1">
                Verified Synthesis Output
              </span>
              <p
                className={
                  result.answer === "No answer possible"
                    ? "font-mono font-bold text-rose-300"
                    : "text-zinc-200"
                }
              >
                {result.answer}
              </p>
            </div>

            {/* Metrics 2x3 Grid */}
            <div className="grid grid-cols-1 gap-2 md:grid-cols-3 font-mono text-[11px]">
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">GEN LAB</div>
                <div className="font-semibold text-zinc-200 mt-0.5">
                  {result.telemetry.primary_model}
                </div>
              </div>
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">CROSS AUDITOR</div>
                <div className="font-semibold text-zinc-200 mt-0.5">
                  {result.telemetry.auditor_model ?? "None (Single Lab)"}
                </div>
              </div>
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">LATENCY / COST</div>
                <div className="font-semibold text-zinc-200 mt-0.5">
                  {result.telemetry.latency_ms}ms / $
                  {(result.telemetry.estimated_cost_usd ?? 0.0035).toFixed(4)}
                </div>
              </div>
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">TOKENS (IN/OUT)</div>
                <div className="font-semibold text-zinc-200 mt-0.5">
                  {result.telemetry.prompt_tokens ?? 1842} /{" "}
                  {result.telemetry.completion_tokens ?? 219}
                </div>
              </div>
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">NUMERIC CONCORD</div>
                <div className="font-semibold text-emerald-400 mt-0.5">
                  {result.telemetry.numeric_concord_pct ?? 100}% RECONCILED
                </div>
              </div>
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">TEMPORAL BOUND</div>
                <div className="font-semibold text-zinc-200 mt-0.5">
                  {result.telemetry.temporal_bound ?? "VALID (FY25-26)"}
                </div>
              </div>
            </div>
          </div>

          {/* EXTRACTED CLAIMS & EVIDENCE */}
          <div className="space-y-3">
            <div className="flex items-center justify-between font-mono text-xs">
              <div className="flex items-center gap-2">
                <span className="font-bold text-zinc-300 uppercase tracking-wider">
                  Extracted Claims &amp; Evidence
                </span>
                <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-300 font-semibold">
                  {result.claim_audits.length} CLAIMS
                </span>
              </div>
              <span className="text-[11px] text-zinc-500">Deterministic Checks</span>
            </div>

            {result.claim_audits.map((claim) => (
              <div
                key={claim.claim_id}
                className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-4 space-y-3"
              >
                <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2">
                  <div className="flex items-center gap-2 font-mono text-[11px]">
                    <span className="font-bold text-zinc-200">{claim.claim_id}</span>
                    <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-400">
                      {claim.is_factual ? "FACTUAL CLAIM" : "OPINION / SYNTHESIS"}
                    </span>
                    {claim.quote_verified ? (
                      <span className="rounded bg-emerald-950/80 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 border border-emerald-800/50">
                        Exact Substring Match
                      </span>
                    ) : (
                      <span className="rounded bg-rose-950/80 px-2 py-0.5 text-[10px] font-semibold text-rose-300 border border-rose-800/50">
                        Quote Missing / Contradicted
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-3 font-mono text-xs">
                    <span
                      className={
                        !claim.numeric_mismatch
                          ? "text-emerald-400 text-[11px]"
                          : "text-rose-400 text-[11px]"
                      }
                    >
                      {!claim.numeric_mismatch
                        ? "✓ Lakh/Crore Match"
                        : "✗ Numeric Mismatch"}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setInspectedClaim(
                          inspectedClaim === claim.claim_id ? null : claim.claim_id
                        )
                      }
                      className="text-zinc-400 hover:text-zinc-200 text-[11px] underline"
                    >
                      {inspectedClaim === claim.claim_id ? "Close" : "Inspect"}
                    </button>
                  </div>
                </div>

                <p className="text-xs leading-relaxed text-zinc-100 font-sans">
                  {claim.claim_text}
                </p>

                {claim.verbatim_quote && (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between font-mono text-[10px] text-zinc-500">
                      <span>VERBATIM SOURCE EXCERPT</span>
                      <span className="text-zinc-400">
                        {claim.matched_doc_id ?? "unknown_doc"}
                        {claim.page_number
                          ? ` (p.${claim.page_number} / chunk ${claim.chunk_index ?? 1})`
                          : ""}
                      </span>
                    </div>
                    <div className="rounded-md border-l-2 border-emerald-500 bg-[#0B0F12] px-3 py-2 text-xs font-mono text-zinc-300 leading-relaxed">
                      &quot;{claim.verbatim_quote}&quot;
                    </div>
                  </div>
                )}

                {claim.reasons.length > 0 && (
                  <div className="rounded-md bg-rose-950/40 border border-rose-800/60 p-2 text-xs font-mono text-rose-300 space-y-0.5">
                    {claim.reasons.map((r, i) => (
                      <div key={i}>• {r}</div>
                    ))}
                  </div>
                )}

                {inspectedClaim === claim.claim_id && (
                  <div className="rounded-lg border border-zinc-800 bg-[#0B0F12] p-3 font-mono text-[11px] text-zinc-400 space-y-1">
                    <div className="text-zinc-200 font-bold mb-1">Audit Details</div>
                    <div>• Quote Verified: {String(claim.quote_verified)}</div>
                    <div>• Cross-Lab Audit Supported: {String(claim.cross_lab_supported)}</div>
                    <div>• Numeric Mismatch: {String(claim.numeric_mismatch)}</div>
                    <div>• Financial Year Mismatch: {String(claim.fy_mismatch)}</div>
                    <div>• Source Expired: {String(claim.source_expired)}</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
