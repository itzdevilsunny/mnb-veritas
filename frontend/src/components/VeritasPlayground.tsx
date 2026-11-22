"use client";

import { useState } from "react";
import { api, jsonInit } from "@/lib/api";
import type { LabProvider, PolicyMode, SourceInput, VerifyResponse } from "@/types/veritas";
import { ClaimCard } from "./ClaimCard";
import { btnPrimary, ErrorNote, inputCls, Label, NO_ANSWER, Panel, VerdictBadge } from "./ui";

const LABS: { id: LabProvider; label: string }[] = [
  { id: "anthropic", label: "Claude" },
  { id: "google", label: "Gemini" },
  { id: "openai", label: "OpenAI" },
  { id: "xai", label: "Grok" },
];

const POLICY_HELP: Record<PolicyMode, string> = {
  strict: "Any unverified claim, expired source or unconfirmed audit → “No answer possible”.",
  balanced: "Drops failing claims; answers with what is verified, flagged as QUALIFY.",
  standard: "Like balanced, but the cross-lab audit is optional.",
};

export default function VeritasPlayground({ onVerified }: { onVerified?: (r: VerifyResponse) => void }) {
  const [query, setQuery] = useState("What was the verified grant allocation for FY 2025-26?");
  const [policy, setPolicy] = useState<PolicyMode>("strict");
  const [labs, setLabs] = useState<LabProvider[]>(["anthropic", "google", "openai", "xai"]);
  const [useInline, setUseInline] = useState(false);
  const [docId, setDocId] = useState("SRC-001");
  const [title, setTitle] = useState("Annual Filing FY 2025-26");
  const [validFrom, setValidFrom] = useState("2025-04-01");
  const [validUntil, setValidUntil] = useState("2027-03-31");
  const [text, setText] = useState(
    "Total verified grant allocation for FY 2025-26 stood at Rs 2.5 crore across 12 districts.",
  );

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);

  const toggleLab = (lab: LabProvider) =>
    setLabs((prev) => (prev.includes(lab) ? (prev.length > 1 ? prev.filter((l) => l !== lab) : prev) : [...prev, lab]));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const inline: SourceInput[] | undefined =
      useInline && text.trim()
        ? [{ doc_id: docId.trim() || "SRC-INLINE", title: title.trim() || "Inline source", text, valid_from: validFrom, valid_until: validUntil || null, is_primary: true }]
        : undefined;
    try {
      const data = await api<VerifyResponse>(
        "/v1/verify",
        jsonInit("POST", { query, policy, preferred_labs: labs, inline_sources: inline }),
      );
      setResult(data);
      onVerified?.(data);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  const abstained = result?.answer === NO_ANSWER;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <form onSubmit={submit} className="space-y-4 rounded-2xl border border-zinc-800 bg-zinc-900/50 p-5 lg:col-span-5">
        <div className="space-y-1.5">
          <Label>Question</Label>
          <textarea rows={3} required value={query} onChange={(e) => setQuery(e.target.value)} className={inputCls}
            placeholder="Ask something that must be backed by an approved source…" />
        </div>

        <div className="space-y-1.5">
          <Label>Policy</Label>
          <div className="grid grid-cols-3 gap-2">
            {(["strict", "balanced", "standard"] as PolicyMode[]).map((m) => (
              <button key={m} type="button" onClick={() => setPolicy(m)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium capitalize transition ${
                  policy === m ? "border-sky-500 bg-sky-500/15 text-sky-200" : "border-zinc-800 bg-zinc-950 text-zinc-400 hover:border-zinc-700"
                }`}>
                {m}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-zinc-500">{POLICY_HELP[policy]}</p>
        </div>

        <div className="space-y-1.5">
          <Label>Generator preference (first available is used)</Label>
          <div className="flex flex-wrap gap-2">
            {LABS.map((l) => (
              <button key={l.id} type="button" onClick={() => toggleLab(l.id)}
                className={`rounded-lg border px-3 py-1 text-xs font-medium transition ${
                  labs.includes(l.id) ? "border-emerald-600/60 bg-emerald-950/50 text-emerald-300" : "border-zinc-800 bg-zinc-950 text-zinc-500"
                }`}>
                {l.label}
              </button>
            ))}
          </div>
        </div>

        <div className="pt-1">
          <label className="flex items-center gap-2 text-xs text-zinc-300">
            <input type="checkbox" checked={useInline} onChange={(e) => setUseInline(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-950 text-sky-500" />
            Supply an inline source just for this run
          </label>
        </div>

        {useInline && (
          <div className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-950/70 p-3 text-xs">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label>Doc ID</Label>
                <input value={docId} onChange={(e) => setDocId(e.target.value)} className={inputCls} />
              </div>
              <div>
                <Label>Title</Label>
                <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputCls} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label>Valid from</Label>
                <input type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} className={inputCls} />
              </div>
              <div>
                <Label>Valid until</Label>
                <input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} className={inputCls} />
              </div>
            </div>
            <div>
              <Label>Source text (must contain the exact quote)</Label>
              <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} className={inputCls} />
            </div>
          </div>
        )}

        <button type="submit" disabled={loading} className={`w-full ${btnPrimary}`}>
          {loading ? "Verifying with MNB Veritas…" : "Run multi-lab verification"}
        </button>
        <ErrorNote message={error} />
      </form>

      <div className="space-y-4 lg:col-span-7">
        {!result && (
          <Panel className="flex min-h-[300px] items-center justify-center text-center text-xs text-zinc-500">
            Submit a question to see claims extracted, quotes cross-checked against sources, deterministic numeric verification and the final report.
          </Panel>
        )}

        {result && (
          <div className="space-y-4">
            <Panel className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <VerdictBadge verdict={result.verdict} />
                  <span className="font-mono text-xs text-zinc-400">{result.audit_id}</span>
                </div>
                <div className="flex items-center gap-3 font-mono text-xs text-zinc-400">
                  <span>{result.telemetry.primary_model}</span>
                  {result.telemetry.auditor_model && <span>· auditor {result.telemetry.auditor_model}</span>}
                  <span>· {result.telemetry.latency_ms}ms</span>
                  <span>· ${result.telemetry.estimated_cost_usd?.toFixed(4)}</span>
                </div>
              </div>

              <div>
                <Label>Answer</Label>
                <p className={`mt-1 text-sm font-medium ${abstained ? "font-mono text-rose-300" : "text-zinc-100"}`}>
                  {result.answer}
                </p>
              </div>

              {result.warnings.length > 0 && (
                <div className="rounded-lg border border-amber-800/60 bg-amber-950/40 p-3 text-xs text-amber-200">
                  <p className="font-semibold uppercase tracking-wider text-[11px] text-amber-300">Policy notes</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-4">
                    {result.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Panel>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <span className="font-mono uppercase tracking-wider">Claims extracted &amp; verified ({result.claim_audits.length})</span>
                <span>Deterministic code outvotes models on numbers &amp; years</span>
              </div>
              <div className="space-y-2">
                {result.claim_audits.map((c) => (
                  <ClaimCard key={c.claim_id} item={c} />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
