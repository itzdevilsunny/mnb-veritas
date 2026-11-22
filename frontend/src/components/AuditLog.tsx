"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AuditRow } from "@/types/veritas";
import { ClaimCard } from "./ClaimCard";
import { btnGhost, Panel, VerdictBadge } from "./ui";

export function AuditLog({ refreshKey = 0 }: { refreshKey?: number }) {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [verdict, setVerdict] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

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
          <button type="button" onClick={() => void load()} className={btnGhost}>
            Refresh
          </button>
        </div>
      </div>
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
