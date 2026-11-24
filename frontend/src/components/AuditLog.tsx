"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AuditChainStatus, AuditRow } from "@/types/veritas";
import { ClaimCard } from "./ClaimCard";
import { btnGhost, Panel, VerdictBadge } from "./ui";

export function AuditLog({ refreshKey = 0 }: { refreshKey?: number }) {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [verdict, setVerdict] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chainStatus, setChainStatus] = useState<AuditChainStatus | null>(null);
  const [chainLoading, setChainLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await api<AuditRow[]>(`/v1/audits?limit=50${verdict ? `&verdict=${verdict}` : ""}`));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load audits");
    } finally {
      setLoading(false);
    }
  }, [verdict]);

  const checkChain = useCallback(async () => {
    setChainLoading(true);
    try {
      const res = await api<AuditChainStatus>("/v1/audits/verify-chain");
      setChainStatus(res);
    } catch {
      // Graceful fallback if backend call fails
    } finally {
      setChainLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void checkChain();
  }, [load, checkChain, refreshKey]);

  return (
    <Panel className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Audit log</h2>
          <p className="text-xs text-zinc-400">Append-only record of every decision, model pairing and quote check.</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={verdict}
            onChange={(e) => setVerdict(e.target.value)}
            aria-label="Filter by verdict"
            className="rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-200"
          >
            <option value="">All verdicts</option>
            {["APPROVE", "QUALIFY", "ABSTAIN", "ESCALATE"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
          <button type="button" onClick={() => { void load(); void checkChain(); }} className={btnGhost}>
            Refresh
          </button>
        </div>
      </div>

      {chainStatus && (
        <div
          className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-xs font-mono ${
            chainStatus.valid
              ? "border-emerald-500/30 bg-emerald-950/20 text-emerald-300"
              : "border-rose-500/30 bg-rose-950/20 text-rose-300"
          }`}
        >
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                chainStatus.valid ? "bg-emerald-400 animate-pulse" : "bg-rose-500"
              }`}
            />
            <span className="font-semibold">
              {chainStatus.valid ? "SHA-256 AUDIT CHAIN VERIFIED" : "CHAIN TAMPER DETECTED"}
            </span>
            <span className="text-zinc-400">
              ({chainStatus.checked_count} logs linked
              {chainStatus.latest_record_hash
                ? ` · Head: ${chainStatus.latest_record_hash.slice(0, 10)}…`
                : ""}
              )
            </span>
            {!chainStatus.valid && chainStatus.first_broken_audit_id && (
              <span className="text-rose-400">
                · Broken at: {chainStatus.first_broken_audit_id}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => void checkChain()}
            disabled={chainLoading}
            className="rounded border border-zinc-700 bg-zinc-900/80 px-2 py-0.5 text-[11px] text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
          >
            {chainLoading ? "Verifying..." : "Re-verify Linkage"}
          </button>
        </div>
      )}

      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
      <div className="overflow-x-auto rounded-xl border border-zinc-800">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-zinc-800 bg-zinc-950 text-zinc-400">
            <tr>
              <th className="px-3 py-2.5">When</th>
              <th className="px-3 py-2.5">Verdict</th>
              <th className="px-3 py-2.5">Question → output</th>
              <th className="px-3 py-2.5">Generator / auditor</th>
              <th className="px-3 py-2.5">Cost</th>
              <th className="px-3 py-2.5 text-right">Claims</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/80 bg-zinc-900/30">
            {rows.map((r) => {
              const isOpen = open === r.audit_id;
              return (
                <Fragment key={r.audit_id}>
                  <tr
                    onClick={() => setOpen(isOpen ? null : r.audit_id)}
                    className="cursor-pointer hover:bg-zinc-800/40"
                  >
                    <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[11px] text-zinc-400">
                      {new Date(r.created_at).toLocaleTimeString()}
                    </td>
                    <td className="px-3 py-2.5">
                      <VerdictBadge verdict={r.verdict} />
                    </td>
                    <td className="max-w-md px-3 py-2.5">
                      <p className="truncate font-medium text-zinc-100">{r.query_text}</p>
                      <p className="truncate text-zinc-400">{r.answer}</p>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[11px] text-zinc-300">
                      {r.primary_model}
                      {r.auditor_model && <span className="text-zinc-500"> · {r.auditor_model}</span>}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[11px] text-zinc-400">
                      ${r.estimated_cost_usd?.toFixed(4) ?? "0.0000"}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-right font-mono text-[11px] text-zinc-400">
                      {r.claim_audits?.length || 0} claims {isOpen ? "▲" : "▼"}
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="bg-zinc-950/60">
                      <td colSpan={6} className="space-y-3 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2 pb-1 border-b border-zinc-800/60">
                          {(r.prev_hash || r.record_hash) && (
                            <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
                              <span className="text-zinc-500 font-semibold tracking-wider uppercase text-[10px]">Audit Chain Proof:</span>
                              {r.prev_hash && (
                                <span className="rounded border border-zinc-800 bg-zinc-900/90 px-2 py-0.5 text-zinc-400">
                                  <span className="text-zinc-500">Prev:</span> {r.prev_hash === "GENESIS" ? "GENESIS" : `${r.prev_hash.slice(0, 12)}…`}
                                </span>
                              )}
                              {r.record_hash && (
                                <span className="rounded border border-emerald-900/50 bg-emerald-950/30 px-2 py-0.5 text-emerald-300">
                                  <span className="text-emerald-500/80">Hash:</span> {r.record_hash.slice(0, 16)}…
                                </span>
                              )}
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-[11px] font-mono">
                            <a
                              href={`/api/audits/${r.audit_id}/certificate?format=pdf`}
                              download={`veritas-certificate-${r.audit_id}.pdf`}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded border border-emerald-700/60 bg-emerald-950/40 px-2.5 py-1 text-emerald-300 hover:bg-emerald-900/50 transition flex items-center gap-1 font-semibold"
                            >
                              <span>📄 Export PDF</span>
                            </a>
                            <a
                              href={`/api/audits/${r.audit_id}/certificate?format=json`}
                              download={`veritas-certificate-${r.audit_id}.json`}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded border border-zinc-700 bg-zinc-900/80 px-2.5 py-1 text-zinc-300 hover:bg-zinc-800 transition flex items-center gap-1"
                            >
                              <span>🔒 JSON Seal</span>
                            </a>
                          </div>
                        </div>
                        <div className="space-y-1">
                          <p className="font-mono text-[11px] text-zinc-500 uppercase tracking-wider">Full answer</p>
                          <p className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-3 text-sm text-zinc-100 whitespace-pre-wrap">
                            {r.answer}
                          </p>
                        </div>
                        {r.claim_audits && r.claim_audits.length > 0 && (
                          <div className="space-y-2">
                            <p className="font-mono text-[11px] text-zinc-500 uppercase tracking-wider">Claims and evidence</p>
                            <div className="grid gap-2">
                              {r.claim_audits.map((c, i) => (
                                <ClaimCard key={c.claim_id || i} item={c} />
                              ))}
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-zinc-500">
                  No audits recorded yet. Run a verification in the Playground.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
