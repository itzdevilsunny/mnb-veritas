"use client";

import React, { useCallback, useEffect, useState } from "react";
import type { AuditLogItem } from "@/types/veritas";

interface AuditLogsViewProps {
  refreshKey?: number;
}

export default function AuditLogsView({ refreshKey = 0 }: AuditLogsViewProps) {
  const [audits, setAudits] = useState<AuditLogItem[]>([]);
  const [filter, setFilter] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchAudits = useCallback(async () => {
    setLoading(true);
    try {
      const qs = filter !== "ALL" ? `?verdict=${filter}` : "";
      const res = await fetch(`/api/audits${qs}`, { cache: "no-store" });
      if (res.ok) {
        setAudits(await res.json());
      }
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void fetchAudits();
  }, [fetchAudits, refreshKey]);

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toISOString().replace("T", " ").slice(0, 19) + " UTC";
    } catch {
      return iso;
    }
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-4">
      {/* Filter Tabs & Refresh Header */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
        <div className="flex items-center gap-1.5 font-mono text-xs">
          {(["ALL", "APPROVE", "QUALIFY", "ABSTAIN"] as const).map((tab) => (
            <button
              type="button"
              key={tab}
              onClick={() => setFilter(tab)}
              className={`rounded px-2.5 py-1 font-semibold transition ${
                filter === tab
                  ? "bg-zinc-800 text-zinc-100 border border-zinc-700"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 font-mono text-[11px] text-zinc-500">
          <span>Persisted: SQLite/Postgres</span>
          <button
            type="button"
            onClick={() => void fetchAudits()}
            className="text-emerald-400 hover:text-emerald-300 transition"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Logs List */}
      <div className="divide-y divide-zinc-800/60">
        {loading ? (
          <div className="py-8 text-center font-mono text-xs text-zinc-500">
            Loading audit records...
          </div>
        ) : audits.length === 0 ? (
          <div className="py-8 text-center font-mono text-xs text-zinc-500">
            No audit records found matching &quot;{filter}&quot;.
          </div>
        ) : (
          audits.map((item) => {
            const isExpanded = expandedId === item.audit_id;
            return (
              <div
                key={item.audit_id}
                onClick={() => setExpandedId(isExpanded ? null : item.audit_id)}
                className="cursor-pointer py-3.5 space-y-1.5 transition hover:bg-[#121820]/60 px-2 rounded-lg"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span className="font-bold text-zinc-200">{item.audit_id}</span>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-bold tracking-wider ${
                        item.verdict === "APPROVE"
                          ? "bg-emerald-950/90 text-emerald-300 border border-emerald-800/60"
                          : item.verdict === "QUALIFY"
                          ? "bg-amber-950/90 text-amber-300 border border-amber-800/60"
                          : "bg-rose-950/90 text-rose-300 border border-rose-800/60"
                      }`}
                    >
                      {item.verdict}
                    </span>
                    {item.verdict === "ABSTAIN" && (
                      <span className="rounded bg-orange-950/80 px-1.5 py-0.5 text-[10px] font-bold text-orange-400 border border-orange-800/60">
                        FAILOVER
                      </span>
                    )}
                  </div>
                  <span className="font-mono text-[11px] text-zinc-500">
                    {formatDate(item.created_at)}
                  </span>
                </div>

                <div className="text-xs text-zinc-200 line-clamp-1">
                  {item.query_text}
                </div>

                <div className="flex items-center justify-between font-mono text-[11px] text-zinc-500">
                  <span className="text-zinc-400">
                    {item.primary_model}
                    {item.auditor_model ? ` → ${item.auditor_model}` : ""}
                  </span>
                  <span>
                    {item.latency_ms}ms • $
                    {(item.estimated_cost_usd ?? 0.0035).toFixed(4)} •{" "}
                    {item.claim_audits?.length ?? 1} claims
                  </span>
                </div>

                {isExpanded && (
                  <div className="mt-3 rounded-lg border border-zinc-800 bg-[#0B0F12] p-3 font-mono text-[11px] text-zinc-400 space-y-2">
                    <div>
                      <span className="text-zinc-500 uppercase">Answer:</span>{" "}
                      <span className="text-zinc-200">{item.answer}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 uppercase">Policy:</span>{" "}
                      <span className="text-zinc-300">{item.policy_applied}</span>
                    </div>
                    {item.warnings && item.warnings.length > 0 && (
                      <div>
                        <span className="text-zinc-500 uppercase">Warnings:</span>{" "}
                        <span className="text-amber-300">{item.warnings.join(" | ")}</span>
                      </div>
                    )}
                    <pre className="overflow-x-auto text-[10px] text-zinc-400 bg-zinc-950 p-2 rounded border border-zinc-900 mt-2">
                      {JSON.stringify(item.claim_audits, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
