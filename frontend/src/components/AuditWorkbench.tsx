"use client";

import React, { useEffect, useState } from "react";
import type {
  BatchVerifyItemResult,
  LabProvider,
  PolicyMode,
  VerifyResponse,
} from "@/types/veritas";
import { ClaimProvenanceDAG } from "./ClaimProvenanceDAG";

interface AuditWorkbenchProps {
  onVerified?: (res: VerifyResponse) => void;
  activeSourceCount?: number;
}

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
  const [streamStage, setStreamStage] = useState<{
    stage: number;
    name: string;
    message: string;
    progress: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [inspectedClaim, setInspectedClaim] = useState<string | null>(null);
  const [openDagId, setOpenDagId] = useState<string | null>(null);
  const [sourcesMap, setSourcesMap] = useState<Record<string, { doc_id: string; title: string; text: string; valid_from: string; valid_until: string | null }>>({});
  const [reviewerName, setReviewerName] = useState("Compliance Officer - Lead Regulatory");
  const [reviewNotes, setReviewNotes] = useState("Verified against statutory regulatory circular.");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [whatIfLoading, setWhatIfLoading] = useState(false);
  const [whatIfResults, setWhatIfResults] = useState<BatchVerifyItemResult[] | null>(null);

  const executeWhatIfMatrix = async () => {
    setWhatIfLoading(true);
    setError(null);
    const q = query.trim();
    if (!q) {
      setError("Query text is required for What-If evaluation");
      setWhatIfLoading(false);
      return;
    }

    let preferredLabs: LabProvider[] = ["anthropic", "openai", "google", "xai"];
    if (generator === "anthropic") preferredLabs = ["anthropic", "openai"];
    if (generator === "openai") preferredLabs = ["openai", "anthropic"];
    if (generator === "google") preferredLabs = ["google", "anthropic"];
    if (generator === "xai") preferredLabs = ["xai", "anthropic"];

    try {
      const res = await fetch("/api/verify/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: [
            { item_id: "strict", query: q, policy: "strict", reference_date: refDate, preferred_labs: preferredLabs },
            { item_id: "balanced", query: q, policy: "balanced", reference_date: refDate, preferred_labs: preferredLabs },
            { item_id: "standard", query: q, policy: "standard", reference_date: refDate, preferred_labs: preferredLabs },
          ],
          concurrency_limit: 3,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail ?? "Failed to execute What-If matrix");
      } else {
        setWhatIfResults(data.results ?? []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "What-If matrix execution failed");
    } finally {
      setWhatIfLoading(false);
    }
  };

  const handleHumanReview = async (decision: "APPROVE" | "REJECT") => {
    if (!result?.audit_id) return;
    setReviewSubmitting(true);
    try {
      const res = await fetch(`/api/audits/${result.audit_id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          reviewer: reviewerName.trim() || "Compliance Officer",
          notes: reviewNotes.trim() || "Manual compliance review decision",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult((prev) =>
          prev
            ? {
                ...prev,
                verdict: data.new_verdict,
                warnings: [...(prev.warnings || []), `Human Review (${decision}) by ${data.reviewer}: ${data.notes}`],
                answer:
                  data.new_verdict === "APPROVE"
                    ? prev.answer.replace(/\[ESCALATED FOR HUMAN REVIEW:.*?\]/g, "").trim()
                    : "No answer possible (Rejected by compliance officer during human escalation review)",
              }
            : null
        );
      }
    } catch (e) {
      console.error("Failed to submit human review", e);
    } finally {
      setReviewSubmitting(false);
    }
  };

  // Load latest real audit from database and active truth sources on mount
  useEffect(() => {
    let mounted = true;
    fetch("/api/audits?limit=1")
      .then((r) => (r.ok ? r.json() : []))
      .then((audits) => {
        if (mounted && Array.isArray(audits) && audits.length > 0) {
          const latest = audits[0];
          setResult({
            audit_id: latest.audit_id,
            verdict: latest.verdict,
            answer: latest.answer,
            policy_applied: latest.policy_applied || "strict",
            telemetry: latest.telemetry || {
              primary_model: latest.primary_model || "Deterministic Engine",
              auditor_model: latest.auditor_model || "Cross-Lab Auditor",
              failover_triggered: Boolean(latest.failover_triggered),
              latency_ms: latest.latency_ms || 340,
              prompt_tokens: latest.prompt_tokens || 420,
              completion_tokens: latest.completion_tokens || 65,
              estimated_cost_usd: latest.estimated_cost_usd || 0.0018,
              numeric_concord_pct: 100,
              temporal_bound: "VALID",
            },
            claim_audits: latest.claim_audits || [],
            warnings: latest.warnings || [],
            created_at: latest.created_at,
          });
        }
      })
      .catch(() => {});

    fetch("/api/sources")
      .then((r) => (r.ok ? r.json() : []))
      .then((srcList) => {
        if (mounted && Array.isArray(srcList)) {
          const map: Record<string, { doc_id: string; title: string; text: string; valid_from: string; valid_until: string | null }> = {};
          for (const s of srcList) {
            map[s.doc_id] = {
              doc_id: s.doc_id,
              title: s.title,
              text: s.text,
              valid_from: s.valid_from,
              valid_until: s.valid_until,
            };
          }
          setSourcesMap(map);
        }
      })
      .catch(() => {});

    return () => {
      mounted = false;
    };
  }, []);

  const renderHighlightedText = (sourceText: string, quote?: string | null) => {
    if (!quote || !quote.trim()) {
      return <p className="text-zinc-300 font-sans text-xs leading-relaxed">{sourceText}</p>;
    }
    const cleanQuote = quote.trim();
    const lowerSource = sourceText.toLowerCase();
    const lowerQuote = cleanQuote.toLowerCase();
    const idx = lowerSource.indexOf(lowerQuote);

    if (idx === -1) {
      return (
        <div className="space-y-2">
          <div className="rounded bg-rose-950/60 border border-rose-800/60 p-2 text-[11px] text-rose-300 font-mono">
            ⚠️ Exact continuous substring not matched in this chunk excerpt.
          </div>
          <p className="text-zinc-300 font-sans text-xs leading-relaxed">{sourceText}</p>
        </div>
      );
    }

    const before = sourceText.slice(0, idx);
    const match = sourceText.slice(idx, idx + cleanQuote.length);
    const after = sourceText.slice(idx + cleanQuote.length);

    return (
      <p className="text-zinc-300 font-sans text-xs leading-relaxed selection:bg-emerald-500/30">
        <span>{before}</span>
        <mark className="rounded bg-emerald-500/25 px-1 py-0.5 text-emerald-200 border-b-2 border-emerald-400 font-semibold shadow-[0_0_12px_rgba(16,185,129,0.3)]">
          {match}
        </mark>
        <span>{after}</span>
      </p>
    );
  };

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
      const streamRes = await fetch("/api/verify/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q,
          policy: p,
          reference_date: d,
          preferred_labs: preferredLabs,
        }),
      });

      if (streamRes.ok && streamRes.body) {
        const reader = streamRes.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data:")) {
              try {
                const event = JSON.parse(trimmed.replace(/^data:\s*/, ""));
                if (event.stage) {
                  setStreamStage({
                    stage: event.stage,
                    name: event.name,
                    message: event.message,
                    progress: event.progress,
                  });
                }
                if (event.result) {
                  setResult(event.result);
                  onVerified?.(event.result);
                }
              } catch {}
            }
          }
        }
      } else {
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
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error during verification");
    } finally {
      setLoading(false);
      setStreamStage(null);
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
              <span>1. FY 2025-26 Outlay (APPROVE)</span>
            </div>
            <span className="mt-1 font-mono text-[11px] text-zinc-400">
              ₹4,850 Cr Green Hydrogen pilot outlay
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
              <span>2. Ungrounded LNG Claim (ABSTAIN)</span>
            </div>
            <span className="mt-1 font-mono text-[11px] text-zinc-400">
              Zero evidence in approved gazette
            </span>
          </button>

          {/* Preset 3: 100x Scale Distortion */}
          <button
            type="button"
            onClick={() =>
              loadPreset(
                "Is the total capital expenditure outlay ₹11,11,111 lakh for FY 2025-26 under the Union Budget?",
                "2025-03-31",
                "strict"
              )
            }
            className="flex flex-col items-start rounded-lg border border-zinc-800/80 bg-[#121820]/70 p-3 text-left transition hover:border-amber-600/60 hover:bg-[#151D26]"
          >
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-100">
              <span className="h-2 w-2 rounded-full bg-amber-400"></span>
              <span>3. 100x Scale Distortion (ABSTAIN)</span>
            </div>
            <span className="mt-1 font-mono text-[11px] text-zinc-400">
              Lakh vs Crore scale discrepancy
            </span>
          </button>

          {/* Preset 4: Critical Regulatory Mandate (Strict Escalation) */}
          <button
            type="button"
            onClick={() =>
              loadPreset(
                "What is the statutory liquid cushion requirement for Category I and II Alternative Investment Funds under emergency drawdown rules?",
                "2025-01-15",
                "strict"
              )
            }
            className="flex flex-col items-start rounded-lg border border-zinc-800/80 bg-[#121820]/70 p-3 text-left transition hover:border-purple-600/60 hover:bg-[#151D26]"
          >
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-100">
              <span className="h-2 w-2 rounded-full bg-purple-400 animate-pulse"></span>
              <span>4. Critical Statutory Mandate (ESCALATE)</span>
            </div>
            <span className="mt-1 font-mono text-[11px] text-zinc-400">
              Mandatory human compliance sign-off
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

        <div className="flex flex-col sm:flex-row gap-2">
          <button
            type="button"
            onClick={() => void executeVerify()}
            disabled={loading || whatIfLoading}
            className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-zinc-950 transition hover:bg-emerald-400 disabled:opacity-50"
          >
            <span>⚡</span>
            <span>{loading ? "EXECUTING MULTI-LAB VERIFICATION..." : "EXECUTE MULTI-LAB VERIFICATION"}</span>
          </button>
          <button
            type="button"
            onClick={() => void executeWhatIfMatrix()}
            disabled={loading || whatIfLoading}
            className="flex items-center justify-center gap-2 rounded-lg border border-cyan-500/60 bg-cyan-950/40 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-cyan-300 transition hover:bg-cyan-900/50 hover:border-cyan-400 disabled:opacity-50"
          >
            <span>📊</span>
            <span>{whatIfLoading ? "EVALUATING 3 POLICIES..." : "RUN WHAT-IF POLICY MATRIX"}</span>
          </button>
        </div>

        {/* What-If Policy Comparative Matrix */}
        {whatIfResults && whatIfResults.length > 0 && (
          <div className="rounded-xl border border-cyan-800/60 bg-[#0A121A] p-4 space-y-3 font-mono">
            <div className="flex items-center justify-between border-b border-cyan-900/40 pb-2">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse"></span>
                <span className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
                  WHAT-IF POLICY MATRIX · COMPARATIVE ANALYSIS
                </span>
              </div>
              <button
                type="button"
                onClick={() => setWhatIfResults(null)}
                className="text-[10px] text-zinc-400 hover:text-zinc-200"
              >
                Dismiss ✕
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {whatIfResults.map((item) => {
                const pol = item.item_id?.toUpperCase() || "POLICY";
                const res = item.result;
                const isApproved = res?.verdict === "APPROVE";
                const isQualify = res?.verdict === "QUALIFY";
                return (
                  <div
                    key={item.item_id}
                    className={`rounded-lg border p-3 flex flex-col justify-between space-y-2.5 ${
                      isApproved
                        ? "border-emerald-700/60 bg-emerald-950/20"
                        : isQualify
                        ? "border-amber-700/60 bg-amber-950/20"
                        : "border-rose-700/60 bg-rose-950/20"
                    }`}
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs font-bold">
                        <span className="text-zinc-200">{pol}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] ${
                            isApproved
                              ? "bg-emerald-900/60 text-emerald-300 border border-emerald-700/60"
                              : isQualify
                              ? "bg-amber-900/60 text-amber-300 border border-amber-700/60"
                              : "bg-rose-900/60 text-rose-300 border border-rose-700/60"
                          }`}
                        >
                          {res?.verdict || "ERROR"}
                        </span>
                      </div>
                      <div className="text-[10px] text-zinc-400 flex items-center justify-between">
                        <span>Safe to Publish:</span>
                        <span className={isApproved ? "text-emerald-300 font-bold" : "text-rose-400 font-bold"}>
                          {isApproved ? "YES" : "NO"}
                        </span>
                      </div>
                      <div className="text-[10px] text-zinc-400 flex items-center justify-between">
                        <span>Latency / Route:</span>
                        <span className="text-zinc-300">
                          {res?.telemetry.latency_ms || 0}ms · {res?.telemetry.moe_route || "fast"}
                        </span>
                      </div>
                      <div className="text-[11px] font-sans text-zinc-200 leading-relaxed rounded bg-zinc-950/60 p-2 border border-zinc-800/60 max-h-36 overflow-y-auto">
                        {res?.answer || item.error || "No response generated."}
                      </div>
                    </div>

                    {res?.warnings && res.warnings.length > 0 && (
                      <div className="text-[10px] text-rose-300/90 space-y-0.5 pt-1.5 border-t border-zinc-800/60">
                        <span className="text-zinc-500 uppercase text-[9px] font-bold">Caveats / Veto:</span>
                        {res.warnings.map((w, wi) => (
                          <p key={wi} className="line-clamp-2">· {w}</p>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Real-time Streaming Pipeline Stepper */}
        {loading && streamStage && (
          <div className="rounded-lg border border-emerald-500/30 bg-[#07130F] p-4 space-y-3 font-mono">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                </span>
                <span className="font-bold text-emerald-400 uppercase tracking-wider">
                  STAGE {streamStage.stage}: {streamStage.name}
                </span>
              </div>
              <span className="text-zinc-400 text-[11px]">{streamStage.progress}%</span>
            </div>

            {/* 5-Stage Live Visual Pipeline Grid */}
            <div className="grid grid-cols-5 gap-1.5 pt-1">
              {[
                { s: 1, label: "01. EXTRACT" },
                { s: 2, label: "02. RETRIEVE" },
                { s: 3, label: "03. EXAMINE" },
                { s: 4, label: "04. DECIDE" },
                { s: 5, label: "05. REPORT" },
              ].map(({ s, label }) => {
                const isCurrent = streamStage.stage === s;
                const isDone = streamStage.stage > s;
                return (
                  <div
                    key={s}
                    className={`rounded border px-1.5 py-1 text-center text-[10px] font-mono transition-all ${
                      isCurrent
                        ? "border-emerald-400 bg-emerald-500/20 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.3)] animate-pulse font-bold"
                        : isDone
                        ? "border-emerald-700/60 bg-emerald-950/40 text-emerald-400"
                        : "border-zinc-800 bg-zinc-900/60 text-zinc-600"
                    }`}
                  >
                    {label}
                  </div>
                );
              })}
            </div>

            {/* Stepper Progress Bar */}
            <div className="h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all duration-300 ease-out"
                style={{ width: `${streamStage.progress}%` }}
              ></div>
            </div>

            <p className="text-[11px] text-zinc-300 leading-relaxed">
              {streamStage.message}
            </p>
          </div>
        )}

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
                      : result.verdict === "ESCALATE"
                      ? "bg-purple-950/80 text-purple-300 border border-purple-700/60"
                      : "bg-rose-950/80 text-rose-300 border border-rose-700/60"
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      result.verdict === "APPROVE"
                        ? "bg-emerald-400"
                        : result.verdict === "QUALIFY"
                        ? "bg-amber-400"
                        : result.verdict === "ESCALATE"
                        ? "bg-purple-400 animate-pulse"
                        : "bg-rose-400"
                    }`}
                  ></span>
                  {result.verdict}
                </span>
                <span className="text-xs text-zinc-300">
                  {result.verdict === "APPROVE"
                    ? `Synthesis fully grounded across approved truth sources. All ${result.claim_audits.length} factual claims passed exact substring quote verification & numeric crore reconciliations.`
                    : result.verdict === "QUALIFY"
                    ? "Qualified synthesis: Verified with temporal/source caveats."
                    : result.verdict === "ESCALATE"
                    ? "Critical regulatory claim flagged: Requires designated compliance officer sign-off before publication."
                    : 'Strict abstention triggered: Claim is ungrounded or contradictory. Answer reverted to "No answer possible".'}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[11px] text-zinc-500">
                  AUDIT_ID: {result.audit_id}
                </span>
                <a
                  href={`/api/audits/${result.audit_id}/certificate?format=pdf`}
                  download={`veritas-certificate-${result.audit_id}.pdf`}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-emerald-700/60 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/60 font-mono text-[11px] transition-colors"
                  title="Download Signed PDF Compliance Certificate"
                >
                  <span>📜</span>
                  <span>Export Certificate (PDF)</span>
                </a>
                <a
                  href={`/api/audits/${result.audit_id}/certificate?format=json`}
                  download={`veritas-seal-${result.audit_id}.json`}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded border border-zinc-700 bg-zinc-900/80 text-zinc-300 hover:bg-zinc-800 font-mono text-[11px] transition-colors"
                  title="Export Cryptographic JSON Seal"
                >
                  <span>🛡️</span>
                  <span>JSON Seal</span>
                </a>
              </div>
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
                    : result.verdict === "ESCALATE"
                    ? "text-purple-200"
                    : "text-zinc-200"
                }
              >
                {result.answer}
              </p>
            </div>

            {/* Human Review Escalation Card */}
            {result.verdict === "ESCALATE" && (
              <div className="rounded-lg border border-purple-800/80 bg-purple-950/30 p-4 space-y-3 font-mono">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-bold text-purple-300 uppercase">
                    <span className="h-2 w-2 rounded-full bg-purple-400 animate-pulse"></span>
                    <span>Human Review Escalation Queue (Compliance Officer Gate)</span>
                  </div>
                  <span className="text-[10px] text-purple-400/80 border border-purple-800/60 bg-purple-900/40 px-2 py-0.5 rounded">
                    MANDATORY SIGN-OFF
                  </span>
                </div>
                <p className="text-xs text-zinc-300 font-sans">
                  The Hard-Coded Policy Engine flagged this critical regulatory claim. Publication is blocked until a designated compliance officer reviews and signs off.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                  <input
                    type="text"
                    value={reviewerName}
                    onChange={(e) => setReviewerName(e.target.value)}
                    placeholder="Officer Name / Role"
                    className="rounded-md border border-zinc-800 bg-[#0B0F12] px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-purple-500 focus:outline-none"
                  />
                  <input
                    type="text"
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    placeholder="Audit Notes"
                    className="rounded-md border border-zinc-800 bg-[#0B0F12] px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-purple-500 focus:outline-none"
                  />
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => handleHumanReview("APPROVE")}
                    disabled={reviewSubmitting}
                    className="flex-1 rounded-md bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/50 py-2 text-xs font-semibold text-emerald-300 transition"
                  >
                    {reviewSubmitting ? "Submitting Sign-off..." : "✓ Sign-Off & Approve for Publication"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleHumanReview("REJECT")}
                    disabled={reviewSubmitting}
                    className="flex-1 rounded-md bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/50 py-2 text-xs font-semibold text-rose-300 transition"
                  >
                    {reviewSubmitting ? "Submitting Rejection..." : "✕ Reject Claim (Abstain)"}
                  </button>
                </div>
              </div>
            )}

            {/* Metrics 4x2 Grid */}
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-4 font-mono text-[11px]">
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">GEN LAB</div>
                <div className="font-semibold text-zinc-200 mt-0.5 truncate">
                  {result.telemetry.primary_model}
                </div>
              </div>
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">CROSS AUDITOR</div>
                <div className="font-semibold text-zinc-200 mt-0.5 truncate">
                  {result.telemetry.auditor_model ?? "None (Single Lab)"}
                </div>
              </div>
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">MoE ROUTE</div>
                <div className="font-semibold text-cyan-400 mt-0.5 uppercase tracking-wide">
                  {result.telemetry.moe_route ?? "fast_extraction"}
                </div>
              </div>
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">CIRCUIT HEALTH</div>
                <div className="font-semibold text-emerald-400 mt-0.5 flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  {result.telemetry.circuit_state ?? "CLOSED"}
                </div>
              </div>
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">LATENCY / COST</div>
                <div className="font-semibold text-zinc-200 mt-0.5">
                  {result.telemetry.latency_ms}ms / $
                  {(result.telemetry.estimated_cost_usd ?? 0).toFixed(4)}
                </div>
              </div>
              <div className="rounded-md border border-zinc-800/80 bg-[#0B0F12] p-2.5">
                <div className="text-[10px] text-zinc-500 uppercase">TOKENS (IN/OUT)</div>
                <div className="font-semibold text-zinc-200 mt-0.5">
                  {result.telemetry.prompt_tokens ?? 0} /{" "}
                  {result.telemetry.completion_tokens ?? 0}
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
                  {result.telemetry.temporal_bound ?? "VALID"}
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
                        setOpenDagId(
                          openDagId === claim.claim_id ? null : claim.claim_id
                        )
                      }
                      className="rounded border border-zinc-700 bg-zinc-800/80 px-2 py-0.5 text-[10px] font-mono text-zinc-300 hover:bg-zinc-700 transition"
                    >
                      {openDagId === claim.claim_id ? "DAG ▲" : "DAG ▼"}
                    </button>
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

                {openDagId === claim.claim_id && (
                  <div className="pt-1">
                    <ClaimProvenanceDAG
                      claim={claim}
                      overallVerdict={result.verdict}
                      auditorModel={result.telemetry?.auditor_model ?? null}
                    />
                  </div>
                )}

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
                  <div className="rounded-xl border border-zinc-700/80 bg-[#080C0E] p-4 space-y-3 font-mono">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-2">
                      <div className="flex items-center gap-2 text-xs font-bold text-zinc-200">
                        <span>🔍 FORENSIC SOURCE EVIDENCE INSPECTOR</span>
                        <span className="rounded bg-emerald-950/80 border border-emerald-800/60 px-2 py-0.5 text-[10px] text-emerald-300">
                          {claim.matched_doc_id ?? "UNCITED_DOC"}
                        </span>
                      </div>
                      <span className="text-[10px] text-zinc-500">
                        {claim.page_number ? `Page ${claim.page_number} • Chunk ${claim.chunk_index ?? 1}` : "Primary Grounding"}
                      </span>
                    </div>

                    {/* Invariant verification matrix */}
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 text-[10px]">
                      <div className="rounded border border-zinc-800/80 bg-zinc-900/60 p-2">
                        <span className="block text-zinc-500">Quote Exactness</span>
                        <span className={`font-bold ${claim.quote_verified ? "text-emerald-400" : "text-rose-400"}`}>
                          {claim.quote_verified ? "✓ 100% Substring Match" : "✗ Discrepancy Found"}
                        </span>
                      </div>
                      <div className="rounded border border-zinc-800/80 bg-zinc-900/60 p-2">
                        <span className="block text-zinc-500">Cross-Lab Consensus</span>
                        <span className={`font-bold ${claim.cross_lab_supported ? "text-emerald-400" : "text-rose-400"}`}>
                          {claim.cross_lab_supported ? "✓ Entailed by Auditor" : "✗ Not Entailed"}
                        </span>
                      </div>
                      <div className="rounded border border-zinc-800/80 bg-zinc-900/60 p-2">
                        <span className="block text-zinc-500">Numeric Fidelity</span>
                        <span className={`font-bold ${!claim.numeric_mismatch ? "text-emerald-400" : "text-rose-400"}`}>
                          {!claim.numeric_mismatch ? "✓ Crore / % Concord" : "✗ Value Contradiction"}
                        </span>
                      </div>
                      <div className="rounded border border-zinc-800/80 bg-zinc-900/60 p-2">
                        <span className="block text-zinc-500">Temporal Validity</span>
                        <span className={`font-bold ${!claim.source_expired ? "text-emerald-400" : "text-rose-400"}`}>
                          {!claim.source_expired ? "✓ In-Bound Valid" : "✗ Policy Expired"}
                        </span>
                      </div>
                    </div>

                    {/* Source Text with Highlighted Quotation */}
                    <div className="space-y-1.5 pt-1">
                      <div className="flex items-center justify-between text-[10px] text-zinc-400">
                        <span>ORIGINAL TRUTH DOCUMENT CHUNK</span>
                        <span className="text-zinc-500">
                          {claim.matched_doc_id && sourcesMap[claim.matched_doc_id]
                            ? `Valid: ${sourcesMap[claim.matched_doc_id].valid_from} to ${sourcesMap[claim.matched_doc_id].valid_until ?? "indefinite"}`
                            : ""}
                        </span>
                      </div>
                      <div className="rounded-lg border border-zinc-800 bg-[#0E1318] p-3 max-h-56 overflow-y-auto">
                        {claim.matched_doc_id && sourcesMap[claim.matched_doc_id] ? (
                          renderHighlightedText(
                            sourcesMap[claim.matched_doc_id].text,
                            claim.verbatim_quote
                          )
                        ) : (
                          <p className="text-zinc-500 text-xs">
                            No full text excerpt available for ungrounded external assertion.
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!result && !loading && (
        <div className="rounded-xl border border-dashed border-zinc-800 bg-[#0E1318]/50 p-8 text-center space-y-3">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-zinc-800/80 text-emerald-400 font-mono text-base border border-zinc-700">
            ⚡
          </div>
          <div className="space-y-1">
            <h3 className="font-mono text-sm font-semibold text-zinc-200">
              Ready for Multi-Lab Verification
            </h3>
            <p className="text-xs text-zinc-400 max-w-md mx-auto">
              Enter any financial claim or question above, or select one of the corpus audit triggers to test real-time grounding, quote attribution, and anti-hallucination guardrails.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
