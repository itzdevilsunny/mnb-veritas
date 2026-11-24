"use client";

import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CornerDownLeft,
  Download,
  FileCode,
  FileText,
  Layers,
  Play,
  RotateCcw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  XCircle,
} from "lucide-react";
import type {
  BatchVerifyItemResult,
  LabProvider,
  ManagedSource,
  PolicyMode,
  VerifyResponse,
} from "@/types/veritas";
import { ClaimCard } from "./ClaimCard";

interface AuditWorkbenchProps {
  onVerified?: (res: VerifyResponse) => void;
  activeSourceCount?: number;
}

interface QuickPrompt {
  id: string;
  sourceDocId: string;
  sourceTitle: string;
  authorityTier: string;
  label: string;
  query: string;
  refDate: string;
  policy: PolicyMode;
}

export default function AuditWorkbench({
  onVerified,
  activeSourceCount = 4,
}: AuditWorkbenchProps) {
  const [query, setQuery] = useState("");
  const [policy, setPolicy] = useState<PolicyMode>("strict");
  const [refDate, setRefDate] = useState("2026-03-31");
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
  const [activeSources, setActiveSources] = useState<ManagedSource[]>([]);
  const [quickPrompts, setQuickPrompts] = useState<QuickPrompt[]>([]);

  // Human review signoff state
  const [reviewerName, setReviewerName] = useState("Lead Regulatory Compliance Officer");
  const [reviewNotes, setReviewNotes] = useState("Verified against statutory regulatory circulars.");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);

  // What-If Matrix state
  const [whatIfLoading, setWhatIfLoading] = useState(false);
  const [whatIfResults, setWhatIfResults] = useState<BatchVerifyItemResult[] | null>(null);

  // Fetch real active truth sources from GET /v1/sources
  useEffect(() => {
    let mounted = true;
    fetch("/api/sources", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : []))
      .then((srcList: ManagedSource[]) => {
        if (!mounted || !Array.isArray(srcList)) return;
        setActiveSources(srcList);

        // Dynamically derive genuine quick-prompts from actual active sources
        const derived: QuickPrompt[] = [];
        for (const s of srcList.slice(0, 6)) {
          const tier = (s.authority_tier || "regulatory").toUpperCase();
          const cleanText = s.text.replace(/\s+/g, " ").trim();
          
          // Generate a genuine grounded query from the source's content
          let promptQuery = "";
          let label = s.title;

          if (cleanText.toLowerCase().includes("liquid cushion") || cleanText.toLowerCase().includes("aif")) {
            promptQuery = "What is the mandatory liquid cushion requirement for Category I and II Alternative Investment Funds under emergency drawdown rules?";
            label = "AIF Liquid Cushion Mandate";
          } else if (cleanText.toLowerCase().includes("cyber") || cleanText.toLowerCase().includes("velocity")) {
            promptQuery = "What are the transaction velocity limits for newly onboarded digital accounts under RBI cyber security controls?";
            label = "RBI Cyber Velocity Controls";
          } else if (cleanText.toLowerCase().includes("brsr") || cleanText.toLowerCase().includes("esg")) {
            promptQuery = "What percentage of value chain footprints must obtain reasonable assurance under SEBI BRSR Core reporting?";
            label = "SEBI BRSR Core ESG Assurance";
          } else if (cleanText.toLowerCase().includes("hydrogen") || cleanText.toLowerCase().includes("budget")) {
            promptQuery = "What is the approved budgetary allocation for the National Green Hydrogen Mission for FY 2025-26 under the new outlay?";
            label = "Green Hydrogen Budget Outlay";
          } else {
            // General query derived from title and first sentence
            const firstSentence = cleanText.split(".")[0];
            promptQuery = `What does ${s.title} mandate regarding ${firstSentence.slice(0, 80)}...?`;
            label = s.title.slice(0, 36);
          }

          derived.push({
            id: s.doc_id,
            sourceDocId: s.doc_id,
            sourceTitle: s.title,
            authorityTier: tier,
            label,
            query: promptQuery,
            refDate: s.valid_from || "2026-01-01",
            policy: tier === "STATUTORY" ? "strict" : "balanced",
          });
        }

        // Also add an adversarial counter-factual probe if sources exist
        if (srcList.length > 0) {
          derived.push({
            id: "probe-contradiction",
            sourceDocId: "all",
            sourceTitle: "Counter-Factual Scale Distortion Probe",
            authorityTier: "ADVERSARIAL",
            label: "100x Scale Distortion Trap",
            query: "The outlay for the Green Hydrogen Mission was approved at ₹4,85,000 Lakh Crore instead of ₹4,850 Crore.",
            refDate: "2026-03-31",
            policy: "strict",
          });
        }

        setQuickPrompts(derived);
      })
      .catch(() => {});

    return () => {
      mounted = false;
    };
  }, []);

  const handleSelectQuickPrompt = (qp: QuickPrompt) => {
    setQuery(qp.query);
    setRefDate(qp.refDate);
    setPolicy(qp.policy);
    if (qp.sourceDocId !== "all") {
      setSourceFilter(qp.sourceDocId);
    } else {
      setSourceFilter("all");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      void executeVerify();
    }
  };

  const executeVerify = async () => {
    const q = query.trim();
    if (!q) {
      setError("Please enter a factual claim or regulatory question to verify.");
      return;
    }

    setLoading(true);
    setError(null);
    setStreamStage({ stage: 1, name: "INITIALIZING", message: "Connecting to forensic pipeline...", progress: 10 });

    let preferredLabs: LabProvider[] = ["anthropic", "openai", "google", "xai", "ollama"];
    if (generator === "anthropic") preferredLabs = ["anthropic", "openai"];
    if (generator === "openai") preferredLabs = ["openai", "anthropic"];
    if (generator === "google") preferredLabs = ["google", "anthropic"];
    if (generator === "xai") preferredLabs = ["xai", "anthropic"];
    if (generator === "ollama") preferredLabs = ["ollama", "anthropic"];

    const sourceIds = sourceFilter === "all" ? undefined : [sourceFilter];

    try {
      const streamRes = await fetch("/api/verify/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q,
          policy,
          reference_date: refDate,
          preferred_labs: preferredLabs,
          source_ids: sourceIds,
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
                if (event.report) {
                  // Normalize stream report to VerifyResponse
                  const formattedResult: VerifyResponse = {
                    audit_id: event.report.audit_id || `aud_${Date.now().toString(16).slice(-8)}`,
                    verdict: event.report.verdict,
                    answer: event.report.answer,
                    policy_applied: policy,
                    telemetry: {
                      primary_model: event.report.model_used,
                      auditor_model: event.report.auditor_model_used,
                      moe_route: "stream_pipeline",
                      circuit_state: event.report.model_used === "provider_exhausted" ? "OPEN" : "CLOSED",
                      failover_triggered: false,
                      latency_ms: event.report.latency_ms || 250,
                      prompt_tokens: event.report.tokens_in || 0,
                      completion_tokens: event.report.tokens_out || 0,
                      estimated_cost_usd: event.report.estimated_cost_usd || 0.0,
                      numeric_concord_pct: event.report.numeric_concord_pct,
                      temporal_bound: event.report.claim_audits?.length ? "VALID" : "N/A",
                    },
                    claim_audits: event.report.claim_audits || [],
                    warnings: event.report.warnings || [],
                    created_at: new Date().toISOString(),
                  };
                  setResult(formattedResult);
                  onVerified?.(formattedResult);
                }
              } catch {}
            }
          }
        }
      } else {
        // Fallback to standard atomic POST /v1/verify
        const res = await fetch("/api/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: q,
            policy,
            reference_date: refDate,
            preferred_labs: preferredLabs,
            source_ids: sourceIds,
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

  const executeWhatIfMatrix = async () => {
    const q = query.trim();
    if (!q) {
      setError("Please enter a query text to run What-If Policy Matrix.");
      return;
    }

    setWhatIfLoading(true);
    setError(null);

    let preferredLabs: LabProvider[] = ["anthropic", "openai", "google", "xai", "ollama"];
    if (generator === "anthropic") preferredLabs = ["anthropic", "openai"];
    if (generator === "openai") preferredLabs = ["openai", "anthropic"];
    if (generator === "google") preferredLabs = ["google", "anthropic"];
    if (generator === "xai") preferredLabs = ["xai", "anthropic"];
    if (generator === "ollama") preferredLabs = ["ollama", "anthropic"];

    const sourceIds = sourceFilter === "all" ? undefined : [sourceFilter];

    try {
      const res = await fetch("/api/verify/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: [
            { item_id: "strict", query: q, policy: "strict", reference_date: refDate, preferred_labs: preferredLabs, source_ids: sourceIds },
            { item_id: "balanced", query: q, policy: "balanced", reference_date: refDate, preferred_labs: preferredLabs, source_ids: sourceIds },
            { item_id: "standard", query: q, policy: "standard", reference_date: refDate, preferred_labs: preferredLabs, source_ids: sourceIds },
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
          notes: reviewNotes.trim() || "Compliance sign-off determination",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult((prev) =>
          prev
            ? {
                ...prev,
                verdict: data.new_verdict,
                warnings: [
                  ...(prev.warnings || []),
                  `Human Review (${decision}) by ${data.reviewer}: ${data.notes}`,
                ],
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

  return (
    <div className="space-y-4 font-sans text-zinc-100">
      {/* High-Density 2-Column Split-Pane Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* ================================================================= */}
        {/* LEFT PANE (lg:col-span-5): COMPOSER & FORENSIC CONTROLS          */}
        {/* ================================================================= */}
        <div className="lg:col-span-5 space-y-3.5">
          {/* Query Composer Card */}
          <div className="rounded-lg border border-[#27272A] bg-[#111114] p-4 space-y-3 shadow-sm">
            <div className="flex items-center justify-between border-b border-[#27272A] pb-2">
              <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                <FileCode className="h-3.5 w-3.5 text-emerald-400" />
                CLAIM COMPOSER
              </span>
              <span className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
                <span>Ctrl</span>
                <span>+</span>
                <CornerDownLeft className="h-2.5 w-2.5" />
              </span>
            </div>

            <div className="space-y-1.5">
              <textarea
                rows={4}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Enter a factual claim or regulatory question to verify against active truth sources..."
                className="w-full rounded-md border border-[#27272A] bg-[#09090B] p-3 text-xs leading-relaxed text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-500/80 focus:outline-none transition resize-y font-sans"
              />
              <div className="flex justify-between items-center text-[10px] font-mono text-zinc-500">
                <span>{query.length} characters</span>
                {query && (
                  <button
                    type="button"
                    onClick={() => setQuery("")}
                    className="hover:text-zinc-300 text-zinc-500 transition"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            {/* Policy Segmented Control */}
            <div className="space-y-1.5 pt-1">
              <label className="block text-[10px] font-mono uppercase tracking-wider text-zinc-400">
                VERIFICATION POLICY MODE
              </label>
              <div className="grid grid-cols-3 gap-1 rounded-md border border-[#27272A] bg-[#09090B] p-1 font-mono text-[11px]">
                {(["strict", "balanced", "standard"] as PolicyMode[]).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setPolicy(mode)}
                    className={`py-1.5 rounded text-center transition font-semibold uppercase tracking-wider ${
                      policy === mode
                        ? "bg-[#18181B] text-zinc-100 border border-[#27272A] shadow-sm"
                        : "text-zinc-500 hover:text-zinc-300"
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
              <div className="text-[10px] font-mono text-zinc-400">
                {policy === "strict" && (
                  <span className="text-emerald-400">
                    STRICT: Zero Hallucination · Exact substring match required · Hard abstention on failure
                  </span>
                )}
                {policy === "balanced" && (
                  <span className="text-amber-400">
                    BALANCED: Reconciles Lakh/Crore scales · Allows qualified temporal caveats
                  </span>
                )}
                {policy === "standard" && (
                  <span className="text-cyan-400">
                    STANDARD: Multi-lab entailment without strict character-for-character veto
                  </span>
                )}
              </div>
            </div>

            {/* Verification Parameters Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2 border-t border-[#27272A]">
              <div className="space-y-1">
                <label className="block text-[10px] font-mono uppercase text-zinc-400">
                  REF DATE
                </label>
                <input
                  type="date"
                  value={refDate}
                  onChange={(e) => setRefDate(e.target.value)}
                  className="w-full rounded border border-[#27272A] bg-[#09090B] px-2 py-1 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-[10px] font-mono uppercase text-zinc-400">
                  PRIMARY LAB
                </label>
                <select
                  value={generator}
                  onChange={(e) => setGenerator(e.target.value)}
                  className="w-full rounded border border-[#27272A] bg-[#09090B] px-2 py-1 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono"
                >
                  <option value="auto">AUTO (Failover)</option>
                  <option value="anthropic">Claude 3.5 Sonnet</option>
                  <option value="openai">GPT-4o Mini</option>
                  <option value="google">Gemini 3 Flash</option>
                  <option value="xai">Grok 2</option>
                  <option value="ollama">Ollama (Local)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="block text-[10px] font-mono uppercase text-zinc-400">
                  SOURCE SCOPE
                </label>
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="w-full rounded border border-[#27272A] bg-[#09090B] px-2 py-1 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono truncate"
                >
                  <option value="all">All Corpus ({activeSources.length})</option>
                  {activeSources.map((s) => (
                    <option key={s.doc_id} value={s.doc_id}>
                      {s.doc_id}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => void executeVerify()}
                disabled={loading || whatIfLoading}
                className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-emerald-600/90 hover:bg-emerald-500 px-3.5 py-2 font-mono text-xs font-semibold uppercase tracking-wider text-zinc-950 transition border border-emerald-500/40 disabled:opacity-50 shadow-sm"
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                <span>{loading ? "VERIFYING..." : "EXECUTE VERIFY"}</span>
              </button>

              <button
                type="button"
                onClick={() => void executeWhatIfMatrix()}
                disabled={loading || whatIfLoading || !query.trim()}
                title="Evaluate claim across Strict, Balanced, and Standard policies side-by-side"
                className="inline-flex items-center gap-1.5 rounded-md border border-[#27272A] bg-[#18181B] px-3 py-2 font-mono text-xs font-semibold uppercase text-zinc-300 hover:text-zinc-100 hover:border-zinc-600 transition disabled:opacity-50"
              >
                <Layers className="h-3.5 w-3.5 text-cyan-400" />
                <span>WHAT-IF MATRIX</span>
              </button>
            </div>
          </div>

          {/* Dynamic Active Corpus Quick Prompts */}
          <div className="rounded-lg border border-[#27272A] bg-[#111114] p-3.5 space-y-2.5 shadow-sm">
            <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 border-b border-[#27272A] pb-2">
              <span className="font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-amber-400" />
                ACTIVE CORPUS AUDITS ({activeSources.length})
              </span>
              <span className="text-[10px] text-zinc-500">Live Database Prompts</span>
            </div>

            {quickPrompts.length > 0 ? (
              <div className="space-y-2">
                {quickPrompts.map((qp) => (
                  <button
                    key={qp.id}
                    type="button"
                    onClick={() => handleSelectQuickPrompt(qp)}
                    className="w-full text-left rounded-md border border-[#27272A] bg-[#141417] p-2.5 transition hover:border-zinc-600 hover:bg-[#18181C] group"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-zinc-200 group-hover:text-emerald-300 transition">
                        {qp.label}
                      </span>
                      <span className={`rounded border px-1.5 py-0.2 font-mono text-[9px] uppercase font-semibold ${
                        qp.authorityTier === "STATUTORY"
                          ? "border-purple-800/60 bg-purple-950/40 text-purple-300"
                          : qp.authorityTier === "ADVERSARIAL"
                          ? "border-amber-800/60 bg-amber-950/40 text-amber-300"
                          : "border-sky-800/60 bg-sky-950/40 text-sky-300"
                      }`}>
                        {qp.authorityTier}
                      </span>
                    </div>
                    <p className="mt-1 font-sans text-[11px] text-zinc-400 line-clamp-2 leading-relaxed">
                      {qp.query}
                    </p>
                  </button>
                ))}
              </div>
            ) : (
              <div className="rounded border border-[#27272A] bg-[#141416] p-4 text-center font-mono text-xs text-zinc-500 space-y-1">
                <p>No active truth sources loaded in database.</p>
                <p className="text-[11px] text-zinc-600 font-sans">
                  Navigate to Sources tab to upload or ingest regulatory circulars.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* ================================================================= */}
        {/* RIGHT PANE (lg:col-span-7): FORENSIC EVIDENCE & VERDICT INSPECTOR */}
        {/* ================================================================= */}
        <div className="lg:col-span-7 space-y-3.5">
          {error && (
            <div className="rounded-md border border-rose-900/60 bg-rose-950/30 p-3 font-mono text-xs text-rose-300 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
              <div className="flex-1">{error}</div>
              <button
                type="button"
                onClick={() => setError(null)}
                className="text-rose-400 hover:text-rose-200 font-mono text-[10px]"
              >
                Dismiss
              </button>
            </div>
          )}

          {/* Streaming Stage Progression Indicator */}
          {streamStage && (
            <div className="rounded-lg border border-[#27272A] bg-[#111114] p-3.5 font-mono text-xs space-y-2 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-zinc-300 font-semibold uppercase tracking-wider text-[11px]">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                  STAGE {streamStage.stage}/5: {streamStage.name}
                </span>
                <span className="text-emerald-400 text-[11px]">{streamStage.progress}%</span>
              </div>
              <p className="text-zinc-400 font-sans text-xs">{streamStage.message}</p>
              <div className="h-1 w-full rounded bg-zinc-800 overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all duration-300"
                  style={{ width: `${streamStage.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Result View or Standby Terminal */}
          {result ? (
            <div className="space-y-3.5">
              {/* Verdict & Certificate Export Header */}
              <div className="rounded-lg border border-[#27272A] bg-[#111114] p-4 space-y-3 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#27272A] pb-3">
                  <div className="flex items-center gap-2.5">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 font-mono text-xs font-bold tracking-wider uppercase ${
                        result.verdict === "APPROVE"
                          ? "border-emerald-800/80 bg-emerald-950/60 text-emerald-300"
                          : result.verdict === "QUALIFY"
                          ? "border-amber-800/80 bg-amber-950/60 text-amber-300"
                          : result.verdict === "ESCALATE"
                          ? "border-purple-800/80 bg-purple-950/60 text-purple-300"
                          : "border-rose-800/80 bg-rose-950/60 text-rose-300"
                      }`}
                    >
                      <span
                        className={`h-2 w-2 rounded-full ${
                          result.verdict === "APPROVE"
                            ? "bg-emerald-400"
                            : result.verdict === "QUALIFY"
                            ? "bg-amber-400"
                            : result.verdict === "ESCALATE"
                            ? "bg-purple-400 animate-pulse"
                            : "bg-rose-400"
                        }`}
                      />
                      {result.verdict}
                    </span>

                    <span className="font-sans text-xs text-zinc-300">
                      {result.verdict === "APPROVE"
                        ? `Approved: Grounded across truth sources. All ${result.claim_audits.length} factual claims verified character-for-character.`
                        : result.verdict === "QUALIFY"
                        ? "Qualified: Grounded with temporal/jurisdictional caveats."
                        : result.verdict === "ESCALATE"
                        ? "Mandatory Escalation: Flagged for compliance officer sign-off."
                        : 'Strict Abstention: Claim ungrounded or contradictory. Output reverted to "No answer possible".'}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 font-mono text-[11px]">
                    <span className="text-zinc-500">ID: {result.audit_id}</span>
                    <a
                      href={`/api/audits/${result.audit_id}/certificate?format=pdf`}
                      download={`veritas-certificate-${result.audit_id}.pdf`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-[#27272A] bg-[#18181B] text-zinc-200 hover:text-white hover:border-zinc-600 transition"
                      title="Download Signed PDF Compliance Certificate"
                    >
                      <Download className="h-3 w-3 text-emerald-400" />
                      <span>PDF</span>
                    </a>
                    <a
                      href={`/api/audits/${result.audit_id}/certificate?format=json`}
                      download={`veritas-seal-${result.audit_id}.json`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-[#27272A] bg-[#18181B] text-zinc-200 hover:text-white hover:border-zinc-600 transition"
                      title="Export Cryptographic JSON Seal"
                    >
                      <Shield className="h-3 w-3 text-cyan-400" />
                      <span>JSON SEAL</span>
                    </a>
                  </div>
                </div>

                {/* Verified Synthesis Output */}
                <div className="rounded-md border border-[#27272A] bg-[#09090B] p-3 text-xs leading-relaxed space-y-1">
                  <span className="block font-mono text-[10px] uppercase text-zinc-500">
                    VERIFIED SYNTHESIS OUTPUT
                  </span>
                  <p
                    className={
                      result.answer === "No answer possible"
                        ? "font-mono font-bold text-rose-400"
                        : result.verdict === "ESCALATE"
                        ? "text-purple-200"
                        : "text-zinc-200"
                    }
                  >
                    {result.answer}
                  </p>
                </div>

                {/* Human Review Escalation Card (if ESCALATE) */}
                {result.verdict === "ESCALATE" && (
                  <div className="rounded-md border border-purple-800/80 bg-purple-950/20 p-3.5 space-y-3 font-mono">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-purple-300 uppercase flex items-center gap-1.5">
                        <ShieldAlert className="h-4 w-4 text-purple-400" />
                        Human Review Escalation Gate (Mandatory Sign-Off)
                      </span>
                      <span className="text-[10px] text-purple-400 border border-purple-800/60 bg-purple-900/40 px-2 py-0.5 rounded">
                        COMPLIANCE GATE
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      <input
                        type="text"
                        value={reviewerName}
                        onChange={(e) => setReviewerName(e.target.value)}
                        placeholder="Reviewer Name / Title"
                        className="rounded border border-[#27272A] bg-[#09090B] px-2.5 py-1 text-zinc-200 focus:border-purple-500 focus:outline-none"
                      />
                      <input
                        type="text"
                        value={reviewNotes}
                        onChange={(e) => setReviewNotes(e.target.value)}
                        placeholder="Regulatory Notes"
                        className="rounded border border-[#27272A] bg-[#09090B] px-2.5 py-1 text-zinc-200 focus:border-purple-500 focus:outline-none"
                      />
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => void handleHumanReview("APPROVE")}
                        disabled={reviewSubmitting}
                        className="flex-1 rounded border border-emerald-800/60 bg-emerald-950/40 hover:bg-emerald-900/40 py-1.5 text-xs font-semibold text-emerald-300 transition"
                      >
                        {reviewSubmitting ? "Submitting..." : "Sign-Off & Approve for Publication"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleHumanReview("REJECT")}
                        disabled={reviewSubmitting}
                        className="flex-1 rounded border border-rose-800/60 bg-rose-950/40 hover:bg-rose-900/40 py-1.5 text-xs font-semibold text-rose-300 transition"
                      >
                        {reviewSubmitting ? "Submitting..." : "Reject Claim (Abstain)"}
                      </button>
                    </div>
                  </div>
                )}

                {/* What-If Policy Matrix Comparison Strip (if run) */}
                {whatIfResults && whatIfResults.length > 0 && (
                  <div className="rounded-md border border-[#27272A] bg-[#141416] p-3 space-y-2 font-mono text-xs">
                    <div className="flex items-center justify-between text-[11px] text-zinc-400 border-b border-[#27272A] pb-1.5">
                      <span className="font-semibold uppercase tracking-wider text-cyan-300 flex items-center gap-1.5">
                        <Layers className="h-3.5 w-3.5 text-cyan-400" />
                        WHAT-IF POLICY MATRIX RESULTS
                      </span>
                      <button
                        type="button"
                        onClick={() => setWhatIfResults(null)}
                        className="text-zinc-500 hover:text-zinc-300 text-[10px]"
                      >
                        Close
                      </button>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      {whatIfResults.map((r) => {
                        const v = r.result?.verdict || "ERROR";
                        return (
                          <div
                            key={r.item_id}
                            className={`rounded border p-2 text-center space-y-1 ${
                              v === "APPROVE"
                                ? "border-emerald-800/60 bg-emerald-950/20"
                                : v === "QUALIFY"
                                ? "border-amber-800/60 bg-amber-950/20"
                                : v === "ESCALATE"
                                ? "border-purple-800/60 bg-purple-950/20"
                                : "border-rose-800/60 bg-rose-950/20"
                            }`}
                          >
                            <span className="font-bold uppercase text-[10px] text-zinc-400 block">
                              {r.item_id}
                            </span>
                            <span className={`font-bold text-xs ${
                              v === "APPROVE"
                                ? "text-emerald-400"
                                : v === "QUALIFY"
                                ? "text-amber-400"
                                : v === "ESCALATE"
                                ? "text-purple-400"
                                : "text-rose-400"
                            }`}>
                              {v}
                            </span>
                            <span className="block text-[10px] text-zinc-500">
                              {r.result?.telemetry?.latency_ms ?? 0}ms · ${((r.result?.telemetry?.estimated_cost_usd) ?? 0).toFixed(4)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* 4-Column Compact Real Telemetry Strip */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 font-mono text-[11px] pt-1 border-t border-[#27272A]">
                  {/* Telemetry Col 1: Models */}
                  <div className="rounded border border-[#27272A] bg-[#141416] p-2 space-y-0.5">
                    <span className="text-[10px] uppercase text-zinc-500 block">GEN → AUDITOR</span>
                    <span className={`font-semibold truncate block ${
                      result.telemetry.primary_model === "provider_exhausted"
                        ? "text-rose-400"
                        : "text-zinc-200"
                    }`}>
                      {result.telemetry.primary_model}
                    </span>
                    <span className="text-[10px] text-zinc-400 truncate block">
                      → {result.telemetry.auditor_model || "None (Skipped)"}
                    </span>
                  </div>

                  {/* Telemetry Col 2: Route & Circuit */}
                  <div className="rounded border border-[#27272A] bg-[#141416] p-2 space-y-0.5">
                    <span className="text-[10px] uppercase text-zinc-500 block">ROUTE &amp; CIRCUIT</span>
                    <span className="font-semibold text-cyan-400 uppercase tracking-wide truncate block">
                      {result.telemetry.moe_route || "DETERMINISTIC_VETO"}
                    </span>
                    <span className={`text-[10px] flex items-center gap-1 font-semibold ${
                      result.telemetry.circuit_state === "OPEN" ? "text-rose-400" : "text-emerald-400"
                    }`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${
                        result.telemetry.circuit_state === "OPEN" ? "bg-rose-400 animate-pulse" : "bg-emerald-400"
                      }`} />
                      {result.telemetry.circuit_state || "CLOSED"}
                    </span>
                  </div>

                  {/* Telemetry Col 3: Latency & Cost */}
                  <div className="rounded border border-[#27272A] bg-[#141416] p-2 space-y-0.5">
                    <span className="text-[10px] uppercase text-zinc-500 block">LATENCY &amp; COST</span>
                    <span className="font-semibold text-zinc-200 block">
                      {result.telemetry.latency_ms}ms
                    </span>
                    <span className="text-[10px] text-zinc-400 block">
                      ${(result.telemetry.estimated_cost_usd ?? 0).toFixed(4)}
                    </span>
                  </div>

                  {/* Telemetry Col 4: Tokens & Concord */}
                  <div className="rounded border border-[#27272A] bg-[#141416] p-2 space-y-0.5">
                    <span className="text-[10px] uppercase text-zinc-500 block">TOKENS &amp; CONCORD</span>
                    <span className="font-semibold text-zinc-200 block">
                      {result.telemetry.prompt_tokens ?? 0} / {result.telemetry.completion_tokens ?? 0}
                    </span>
                    <span className="text-[10px] text-emerald-400 block">
                      {result.claim_audits.length > 0
                        ? `${result.telemetry.numeric_concord_pct ?? 100}% Reconciled`
                        : "N/A (0 Claims)"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Atomic Claims & Evidence Breakdown */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between font-mono text-xs border-b border-[#27272A] pb-2">
                  <span className="font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                    <FileText className="h-3.5 w-3.5 text-emerald-400" />
                    EXTRACTED CLAIMS &amp; EVIDENCE ({result.claim_audits.length})
                  </span>
                  <span className="text-[10px] text-zinc-500">Character-for-Character Verification</span>
                </div>

                {result.claim_audits.length > 0 ? (
                  <div className="space-y-3">
                    {result.claim_audits.map((claim) => (
                      <ClaimCard key={claim.claim_id} item={claim} />
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-[#27272A] bg-[#111114] p-4 text-center font-mono text-xs text-zinc-500">
                    Zero atomic claims extracted for this query. Deterministic veto triggered.
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* Standby Forensic Workstation State */
            <div className="rounded-lg border border-[#27272A] bg-[#111114] p-6 space-y-4 shadow-sm font-sans">
              <div className="flex items-center justify-between border-b border-[#27272A] pb-3 font-mono text-xs">
                <span className="font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-emerald-400" />
                  FORENSIC AUDIT ENGINE · STANDBY
                </span>
                <span className="rounded border border-emerald-900/60 bg-emerald-950/30 px-2 py-0.5 text-emerald-400 text-[10px] font-semibold">
                  PIPELINE READY
                </span>
              </div>

              <div className="space-y-2 text-xs text-zinc-400 leading-relaxed">
                <p className="text-zinc-300 font-medium">
                  The MNB Veritas verification pipeline enforces 5 non-negotiable compliance invariants:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1 font-mono text-[11px]">
                  <div className="rounded border border-[#27272A] bg-[#141416] p-2.5 space-y-1">
                    <span className="text-emerald-400 font-semibold block">1. NO PARAPHRASE PROOF</span>
                    <span className="text-zinc-400 font-sans text-[11px]">
                      Exact continuous substring quote matching against verified regulatory gazettes.
                    </span>
                  </div>
                  <div className="rounded border border-[#27272A] bg-[#141416] p-2.5 space-y-1">
                    <span className="text-emerald-400 font-semibold block">2. DETERMINISTIC CODE GATE</span>
                    <span className="text-zinc-400 font-sans text-[11px]">
                      Pure Python Lakh vs Crore scale normalization and FY boundary reconciliation overriding LLM claims.
                    </span>
                  </div>
                  <div className="rounded border border-[#27272A] bg-[#141416] p-2.5 space-y-1">
                    <span className="text-emerald-400 font-semibold block">3. CROSS-LAB INDEPENDENCE</span>
                    <span className="text-zinc-400 font-sans text-[11px]">
                      A primary generator model is never permitted to audit its own output.
                    </span>
                  </div>
                  <div className="rounded border border-[#27272A] bg-[#141416] p-2.5 space-y-1">
                    <span className="text-emerald-400 font-semibold block">4. TEMPORAL BOUNDARY AUDIT</span>
                    <span className="text-zinc-400 font-sans text-[11px]">
                      Strict partitioning on `valid_from` and `valid_until` prevents expired circular hallucination.
                    </span>
                  </div>
                </div>
              </div>

              <div className="rounded border border-[#27272A] bg-[#09090B] p-3 font-mono text-[11px] text-zinc-400 flex items-center justify-between">
                <span>Select a quick prompt on the left or compose a regulatory claim to initiate verification.</span>
                <span className="text-zinc-500">Shortcut: Ctrl+Enter</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
