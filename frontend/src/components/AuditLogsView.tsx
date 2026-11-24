"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Download,
  FileCheck2,
  FileSearch,
  FileText,
  Link2,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type { AuditChainStatus, AuditLogItem } from "@/types/veritas";

interface AuditLogsViewProps {
  refreshKey?: number;
}

type VerdictFilter = "ALL" | "APPROVE" | "QUALIFY" | "ABSTAIN" | "ESCALATE";

export default function AuditLogsView({ refreshKey = 0 }: AuditLogsViewProps) {
  const [audits, setAudits] = useState<AuditLogItem[]>([]);
  const [filter, setFilter] = useState<VerdictFilter>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // SHA-256 chain verification state
  const [chainStatus, setChainStatus] = useState<AuditChainStatus | null>(null);
  const [chainLoading, setChainLoading] = useState<boolean>(false);

  const fetchAudits = useCallback(async () => {
    setLoading(true);
    try {
      const qs = filter !== "ALL" ? `?verdict=${filter}&limit=150` : "?limit=150";
      const res = await fetch(`/api/audits${qs}`, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`Failed to load audits (HTTP ${res.status})`);
      }
      const data: AuditLogItem[] = await res.json();
      setAudits(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit records");
      setAudits([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  const verifyChain = useCallback(async () => {
    setChainLoading(true);
    try {
      const res = await fetch("/api/audits/verify-chain", { cache: "no-store" });
      if (res.ok) {
        const data: AuditChainStatus = await res.json();
        setChainStatus(data);
      }
    } catch {
      // Non-fatal if chain verification is unreachable
    } finally {
      setChainLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchAudits();
    void verifyChain();
  }, [fetchAudits, verifyChain, refreshKey]);

  const copyToClipboard = (text: string, id: string) => {
    void navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toISOString().replace("T", " ").slice(0, 19) + " UTC";
    } catch {
      return iso;
    }
  };

  // Real search filtering over query, audit_id, and models
  const filteredAudits = useMemo(() => {
    if (!searchQuery.trim()) return audits;
    const q = searchQuery.toLowerCase().trim();
    return audits.filter(
      (a) =>
        a.audit_id.toLowerCase().includes(q) ||
        a.query_text?.toLowerCase().includes(q) ||
        a.primary_model?.toLowerCase().includes(q) ||
        (a.auditor_model && a.auditor_model.toLowerCase().includes(q)) ||
        (a.record_hash && a.record_hash.toLowerCase().includes(q))
    );
  }, [audits, searchQuery]);

  const exportToJson = () => {
    if (!filteredAudits.length) return;
    const blob = new Blob([JSON.stringify(filteredAudits, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mnb_veritas_audit_trail_${filter.toLowerCase()}_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportToCsv = () => {
    if (!filteredAudits.length) return;
    const headers = [
      "audit_id",
      "verdict",
      "policy_applied",
      "primary_model",
      "auditor_model",
      "latency_ms",
      "estimated_cost_usd",
      "claims_count",
      "prev_hash",
      "record_hash",
      "created_at",
      "query_text",
      "answer",
    ];
    const rows = filteredAudits.map((a) => [
      `"${a.audit_id}"`,
      `"${a.verdict}"`,
      `"${a.policy_applied}"`,
      `"${a.primary_model ?? ""}"`,
      `"${a.auditor_model ?? ""}"`,
      a.latency_ms ?? 0,
      Number(a.estimated_cost_usd ?? 0).toFixed(4),
      a.claim_audits?.length ?? 0,
      `"${a.prev_hash ?? ""}"`,
      `"${a.record_hash ?? ""}"`,
      `"${a.created_at}"`,
      `"${(a.query_text || "").replace(/"/g, '""')}"`,
      `"${(a.answer || "").replace(/"/g, '""')}"`,
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mnb_veritas_audit_trail_${filter.toLowerCase()}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case "APPROVE":
        return "bg-emerald-950/80 text-emerald-300 border border-emerald-800/70";
      case "QUALIFY":
        return "bg-amber-950/80 text-amber-300 border border-amber-800/70";
      case "ABSTAIN":
        return "bg-rose-950/80 text-rose-300 border border-rose-800/70";
      case "ESCALATE":
        return "bg-purple-950/80 text-purple-300 border border-purple-800/70";
      default:
        return "bg-zinc-900 text-zinc-300 border border-zinc-700";
    }
  };

  return (
    <div className="space-y-4 font-sans text-zinc-100">
      {/* Cryptographic SHA-256 Ledger Banner */}
      {chainStatus && (
        <div
          className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3.5 py-2.5 font-mono text-xs shadow-sm ${
            chainStatus.valid
              ? "border-emerald-900/60 bg-emerald-950/30 text-emerald-300"
              : "border-rose-900/60 bg-rose-950/30 text-rose-300"
          }`}
        >
          <div className="flex flex-wrap items-center gap-2.5">
            <span
              className={`h-2 w-2 rounded-full shrink-0 ${
                chainStatus.valid ? "bg-emerald-400 animate-pulse" : "bg-rose-500"
              }`}
            />
            <span className="font-semibold tracking-wider uppercase text-[11px] flex items-center gap-1.5">
              {chainStatus.valid ? (
                <>
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                  SHA-256 AUDIT CHAIN VERIFIED
                </>
              ) : (
                <>
                  <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
                  CHAIN TAMPER DETECTED
                </>
              )}
            </span>
            <span className="text-zinc-400 text-[11px] tabular-nums">
              ({chainStatus.checked_count} logs cryptographically sealed
              {chainStatus.latest_record_hash
                ? ` · Head: ${chainStatus.latest_record_hash.slice(0, 10)}…`
                : ""}
              )
            </span>
            {!chainStatus.valid && chainStatus.first_broken_audit_id && (
              <span className="rounded bg-rose-900/60 px-1.5 py-0.5 text-[10px] text-rose-200 border border-rose-700/60 font-semibold">
                Broken at: {chainStatus.first_broken_audit_id}
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={() => void verifyChain()}
            disabled={chainLoading}
            className="inline-flex items-center gap-1.5 rounded border border-[#27272A] bg-[#18181B] px-2.5 py-1 text-[11px] font-semibold text-zinc-300 hover:text-zinc-100 hover:border-zinc-600 transition disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${chainLoading ? "animate-spin text-emerald-400" : ""}`} />
            <span>{chainLoading ? "Re-verifying..." : "Re-verify Linkage"}</span>
          </button>
        </div>
      )}

      {/* Main Ledger Container */}
      <div className="rounded-lg border border-[#27272A] bg-[#111114] p-4 space-y-4 shadow-sm">
        {/* Header Controls & Filter Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#27272A] pb-3.5">
          {/* Verdict Filter Segmented Control */}
          <div className="flex flex-wrap items-center gap-1 font-mono text-xs">
            {(["ALL", "APPROVE", "QUALIFY", "ABSTAIN", "ESCALATE"] as const).map((tab) => (
              <button
                type="button"
                key={tab}
                onClick={() => setFilter(tab)}
                className={`rounded px-2.5 py-1 font-semibold transition uppercase tracking-wider text-[11px] ${
                  filter === tab
                    ? "bg-[#18181B] text-zinc-100 border border-[#27272A] shadow-sm"
                    : "text-zinc-500 hover:text-zinc-300 hover:bg-[#141416]"
                }`}
              >
                {tab}
              </button>
            ))}
            <span className="ml-2 rounded border border-[#27272A] bg-[#09090B] px-2 py-0.5 text-[10px] text-zinc-400 font-mono tabular-nums">
              {filteredAudits.length} Records
            </span>
          </div>

          {/* Search Input & Action Controls */}
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-500 pointer-events-none" />
              <input
                type="text"
                placeholder="Search audit ID, prompt, model..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-48 sm:w-64 rounded-md border border-[#27272A] bg-[#09090B] py-1.5 pl-8 pr-2.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-emerald-500/80 focus:outline-none transition font-sans"
              />
            </div>

            <button
              type="button"
              onClick={exportToJson}
              disabled={!filteredAudits.length}
              className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-2.5 py-1.5 text-[11px] font-semibold text-zinc-300 hover:border-emerald-500/60 hover:text-emerald-300 transition disabled:opacity-40"
            >
              <Download className="h-3 w-3" />
              <span>Export JSON</span>
            </button>

            <button
              type="button"
              onClick={exportToCsv}
              disabled={!filteredAudits.length}
              className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-2.5 py-1.5 text-[11px] font-semibold text-zinc-300 hover:border-emerald-500/60 hover:text-emerald-300 transition disabled:opacity-40"
            >
              <FileText className="h-3 w-3" />
              <span>Export CSV</span>
            </button>

            <button
              type="button"
              onClick={() => {
                void fetchAudits();
                void verifyChain();
              }}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-2.5 py-1.5 text-[11px] font-semibold text-emerald-400 hover:bg-[#1f1f23] transition disabled:opacity-50"
            >
              <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded border border-rose-900/60 bg-rose-950/30 p-3 font-mono text-xs text-rose-300">
            <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Ledger Entries List */}
        <div className="space-y-2.5">
          {loading ? (
            <div className="py-12 text-center font-mono text-xs text-zinc-500 space-y-2">
              <RefreshCw className="h-5 w-5 animate-spin mx-auto text-emerald-400" />
              <div>Loading authentic forensic audit trail from database...</div>
            </div>
          ) : filteredAudits.length === 0 ? (
            <div className="rounded-lg border border-[#27272A] bg-[#09090B] py-12 px-4 text-center font-mono text-xs text-zinc-400 space-y-2">
              <FileSearch className="h-8 w-8 mx-auto text-zinc-600" />
              <div className="font-semibold text-zinc-300">
                No audit records found matching &quot;{filter}&quot;
                {searchQuery ? ` with search term "${searchQuery}"` : ""}.
              </div>
              <p className="text-[11px] text-zinc-500 max-w-md mx-auto">
                All records rendered in this ledger are cryptographically bound to real pipeline executions. Run a verification query in the Audit Workbench or execute the Benchmark Lab to populate the audit chain.
              </p>
            </div>
          ) : (
            filteredAudits.map((item) => {
              const isExpanded = expandedId === item.audit_id;
              const hasPrev = Boolean(item.prev_hash);
              const hasRecord = Boolean(item.record_hash);

              return (
                <div
                  key={item.audit_id}
                  className="rounded-lg border border-[#27272A] bg-[#141416] p-3 space-y-2 transition hover:border-zinc-700 shadow-sm font-sans"
                >
                  {/* Row Top Header: ID, Verdict, Policy, Chain Proof & Timestamp */}
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#27272A] pb-2 font-mono text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      {/* Audit ID with Copy */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          copyToClipboard(item.audit_id, item.audit_id);
                        }}
                        title="Click to copy Audit ID"
                        className="font-bold text-zinc-100 hover:text-emerald-400 transition flex items-center gap-1"
                      >
                        <span>{item.audit_id}</span>
                        {copiedId === item.audit_id ? (
                          <Check className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <Copy className="h-3 w-3 text-zinc-500 opacity-60 hover:opacity-100" />
                        )}
                      </button>

                      {/* Verdict Badge */}
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${getVerdictBadge(
                          item.verdict
                        )}`}
                      >
                        {item.verdict}
                      </span>

                      {/* Policy Mode Badge */}
                      <span className="rounded border border-[#27272A] bg-[#18181B] px-1.5 py-0.5 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                        {item.policy_applied || "STRICT"}
                      </span>

                      {/* Failover badge strictly if triggered */}
                      {item.failover_triggered && (
                        <span className="rounded border border-amber-800/60 bg-amber-950/80 px-1.5 py-0.5 text-[10px] font-bold text-amber-300">
                          FAILOVER
                        </span>
                      )}

                      {/* Cryptographic Linkage Hash Pill */}
                      {(hasPrev || hasRecord) && (
                        <span className="hidden sm:inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#09090B] px-2 py-0.5 text-[10px] text-zinc-400">
                          <Link2 className="h-2.5 w-2.5 text-emerald-400" />
                          <span>
                            {item.prev_hash === "GENESIS"
                              ? "GENESIS"
                              : `${(item.prev_hash || "").slice(0, 8)}…`}
                          </span>
                          <span className="text-zinc-600">→</span>
                          <span className="text-emerald-400">
                            {item.record_hash ? `${item.record_hash.slice(0, 8)}…` : "SEALED"}
                          </span>
                        </span>
                      )}
                    </div>

                    {/* Exact Timestamp */}
                    <span className="text-[11px] text-zinc-500 tabular-nums">
                      {formatDate(item.created_at)}
                    </span>
                  </div>

                  {/* Row Middle: Query Text */}
                  <div className="text-xs font-medium text-zinc-200 leading-snug">
                    {item.query_text}
                  </div>

                  {/* Row Bottom: Model Pair, Real Telemetry & Action Buttons */}
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1 font-mono text-[11px]">
                    {/* Models & Failover Info */}
                    <div className="text-zinc-400 flex items-center gap-1.5">
                      <span
                        className={
                          item.primary_model === "provider_exhausted"
                            ? "text-rose-400 font-semibold"
                            : "text-zinc-300"
                        }
                      >
                        {item.primary_model}
                      </span>
                      <span className="text-zinc-600">→</span>
                      <span className="text-zinc-400">
                        {item.auditor_model || "None (Skipped)"}
                      </span>
                    </div>

                    {/* Real Telemetry & Export Links */}
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-zinc-400 tabular-nums">
                        {item.latency_ms ?? 0}ms · $
                        {Number(item.estimated_cost_usd ?? 0).toFixed(4)} ·{" "}
                        <span className="text-zinc-300 font-semibold">
                          {item.claim_audits?.length ?? 0}
                        </span>{" "}
                        claims
                      </span>

                      {/* Export PDF Button */}
                      <a
                        href={`/api/audits/${item.audit_id}/certificate?format=pdf`}
                        download={`veritas-compliance-certificate-${item.audit_id}.pdf`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded border border-emerald-800/60 bg-emerald-950/40 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 hover:bg-emerald-900/60 transition"
                      >
                        <Download className="h-2.5 w-2.5 text-emerald-400" />
                        <span>PDF</span>
                      </a>

                      {/* Export JSON Seal Button */}
                      <a
                        href={`/api/audits/${item.audit_id}/certificate?format=json`}
                        download={`veritas-seal-${item.audit_id}.json`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-[10px] font-semibold text-zinc-300 hover:text-zinc-100 hover:border-zinc-600 transition"
                      >
                        <Shield className="h-2.5 w-2.5 text-cyan-400" />
                        <span>JSON Seal</span>
                      </a>

                      {/* Expand / Collapse Details Drawer */}
                      <button
                        type="button"
                        onClick={() => setExpandedId(isExpanded ? null : item.audit_id)}
                        className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-[10px] font-semibold text-zinc-300 hover:text-zinc-100 hover:border-zinc-600 transition"
                      >
                        <span>{isExpanded ? "Collapse" : "Details"}</span>
                        {isExpanded ? (
                          <ChevronUp className="h-3 w-3 text-zinc-400" />
                        ) : (
                          <ChevronDown className="h-3 w-3 text-zinc-400" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Expanded Forensic Drawer */}
                  {isExpanded && (
                    <div className="mt-3 rounded-md border border-[#27272A] bg-[#09090B] p-3.5 font-mono text-xs text-zinc-300 space-y-3">
                      {/* Synthesized Answer */}
                      <div className="space-y-1">
                        <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold block">
                          VERIFIED SYNTHESIS ANSWER
                        </span>
                        <div className="rounded border border-[#27272A] bg-[#111114] p-2.5 font-sans text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap">
                          {item.answer}
                        </div>
                      </div>

                      {/* Cryptographic SHA-256 Hashes */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                        <div className="rounded border border-[#27272A] bg-[#111114] p-2 space-y-1">
                          <span className="text-[10px] uppercase text-zinc-500 font-semibold block">
                            PRIOR RECORD HASH (PREV_HASH)
                          </span>
                          <div className="flex items-center justify-between font-mono text-zinc-400 break-all">
                            <span>{item.prev_hash || "GENESIS"}</span>
                            {item.prev_hash && item.prev_hash !== "GENESIS" && (
                              <button
                                type="button"
                                onClick={() => copyToClipboard(item.prev_hash!, `prev_${item.audit_id}`)}
                                title="Copy Prev Hash"
                                className="ml-1 text-zinc-500 hover:text-zinc-300 shrink-0"
                              >
                                {copiedId === `prev_${item.audit_id}` ? (
                                  <Check className="h-3 w-3 text-emerald-400" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </button>
                            )}
                          </div>
                        </div>

                        <div className="rounded border border-[#27272A] bg-[#111114] p-2 space-y-1">
                          <span className="text-[10px] uppercase text-emerald-500 font-semibold block">
                            CURRENT RECORD HASH (SHA-256 SEAL)
                          </span>
                          <div className="flex items-center justify-between font-mono text-emerald-300 break-all">
                            <span>{item.record_hash || "PENDING"}</span>
                            {item.record_hash && (
                              <button
                                type="button"
                                onClick={() => copyToClipboard(item.record_hash!, `rec_${item.audit_id}`)}
                                title="Copy Record Hash"
                                className="ml-1 text-zinc-500 hover:text-zinc-300 shrink-0"
                              >
                                {copiedId === `rec_${item.audit_id}` ? (
                                  <Check className="h-3 w-3 text-emerald-400" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Warnings if any */}
                      {item.warnings && item.warnings.length > 0 && (
                        <div className="rounded border border-amber-900/60 bg-amber-950/30 p-2.5 space-y-1">
                          <span className="text-[10px] uppercase tracking-wider text-amber-400 font-semibold block">
                            COMPLIANCE WARNINGS ({item.warnings.length})
                          </span>
                          <ul className="list-disc list-inside text-[11px] text-amber-200 space-y-0.5">
                            {item.warnings.map((w, idx) => (
                              <li key={idx}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Atomic Claims & Evidence Provenance */}
                      <div className="space-y-1.5 pt-1">
                        <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold flex items-center gap-1.5">
                          <FileCheck2 className="h-3.5 w-3.5 text-emerald-400" />
                          CLAIM PROVENANCE &amp; VERBATIM QUOTES ({item.claim_audits?.length ?? 0})
                        </span>

                        {item.claim_audits && item.claim_audits.length > 0 ? (
                          <div className="space-y-2">
                            {item.claim_audits.map((claim, idx) => (
                              <div
                                key={claim.claim_id || idx}
                                className="rounded border border-[#27272A] bg-[#111114] p-2.5 space-y-1.5 text-xs font-sans"
                              >
                                <div className="flex items-center justify-between font-mono text-[10px] border-b border-[#27272A] pb-1">
                                  <span className="font-bold text-zinc-300">
                                    {claim.claim_id || `CLAIM-${idx + 1}`}
                                  </span>
                                  <div className="flex items-center gap-1.5">
                                    {claim.quote_verified ? (
                                      <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold">
                                        <CheckCircle2 className="h-3 w-3" />
                                        <span>Quote Verified</span>
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-1 text-rose-400 font-semibold">
                                        <XCircle className="h-3 w-3" />
                                        <span>Quote Unverified</span>
                                      </span>
                                    )}
                                    {claim.numeric_mismatch && (
                                      <span className="rounded bg-rose-950/80 px-1 py-0.2 text-rose-300 border border-rose-800/60 font-semibold">
                                        Scale Mismatch
                                      </span>
                                    )}
                                    {claim.fy_mismatch && (
                                      <span className="rounded bg-rose-950/80 px-1 py-0.2 text-rose-300 border border-rose-800/60 font-semibold">
                                        FY Mismatch
                                      </span>
                                    )}
                                  </div>
                                </div>

                                <div className="text-zinc-200 text-xs">
                                  <span className="text-zinc-500 font-mono text-[10px] uppercase mr-1">
                                    Claim:
                                  </span>
                                  {claim.claim_text}
                                </div>

                                {claim.verbatim_quote && (
                                  <div className="rounded border border-emerald-950 bg-emerald-950/20 p-2 text-xs text-emerald-200 font-mono">
                                    <span className="text-emerald-500 text-[10px] uppercase block">
                                      VERBATIM SOURCE QUOTE:
                                    </span>
                                    &ldquo;{claim.verbatim_quote}&rdquo;
                                    {claim.matched_doc_id && (
                                      <div className="text-[10px] text-zinc-400 mt-1 flex items-center gap-2">
                                        <span>Source: {claim.matched_doc_id}</span>
                                        {claim.page_number && (
                                          <span>· Page {claim.page_number}</span>
                                        )}
                                        {claim.chunk_index !== undefined && (
                                          <span>· Chunk {claim.chunk_index}</span>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                )}

                                {claim.reasons && claim.reasons.length > 0 && (
                                  <div className="text-[11px] text-rose-300 font-mono">
                                    <span className="text-rose-500 uppercase text-[10px]">
                                      Rejection Reasons:
                                    </span>{" "}
                                    {claim.reasons.join(" · ")}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="rounded border border-[#27272A] bg-[#111114] p-3 text-center text-[11px] text-zinc-500 font-mono">
                            Zero atomic claims extracted for this query. Deterministic veto triggered.
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
