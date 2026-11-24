"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  FileCode,
  FileText,
  Filter,
  Layers,
  Play,
  Plus,
  RotateCcw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  Trash2,
  XCircle,
} from "lucide-react";
import type {
  BenchmarkCaseResult,
  BenchmarkSuiteReport,
  CustomTestCase,
  PolicyMode,
} from "@/types/veritas";

const STANDARD_PRESETS: Array<{
  name: string;
  category: string;
  query: string;
  policy: PolicyMode;
  expected_verdict: "APPROVE" | "ABSTAIN" | "QUALIFY" | "ESCALATE";
  test_goal: string;
}> = [
  {
    name: "SEBI BRSR Core ESG Footprint Assurance",
    category: "STATUTORY_MANDATE",
    query: "What percentage of value chain footprints must obtain reasonable assurance under SEBI BRSR Core reporting for top listed entities?",
    policy: "strict",
    expected_verdict: "APPROVE",
    test_goal: "Validates regulatory circular quote extraction and mandated value-chain ESG assurance threshold.",
  },
  {
    name: "RBI Digital Account Velocity Thresholds",
    category: "REGULATORY_RULE",
    query: "What are the cooling-off transaction limits for newly provisioned digital accounts under RBI cyber security directives?",
    policy: "strict",
    expected_verdict: "APPROVE",
    test_goal: "Enforces quantitative limit reconciliation against master digital banking security circulars.",
  },
  {
    name: "Adversarial 100x Scale Inflation Trap",
    category: "SCALE_DISTORTION",
    query: "The cabinet approved ₹4,85,000 Lakh Crore for the Green Hydrogen Mission outlay instead of ₹4,850 Crore.",
    policy: "strict",
    expected_verdict: "ABSTAIN",
    test_goal: "Enforces pure-Python lakh vs crore scale discord trap rejection.",
  },
  {
    name: "Offshore Sovereign Collateral Hallucination Probe",
    category: "HALLUCINATION_TRAP",
    query: "Explain India's bilateral sovereign counter-guarantees for East African LNG infrastructure projects.",
    policy: "strict",
    expected_verdict: "ABSTAIN",
    test_goal: "Enforces strict abstention on ungrounded claims with zero evidence in gazettes.",
  },
];

export default function BenchmarkRunner() {
  const [report, setReport] = useState<BenchmarkSuiteReport | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);

  // Custom test suite state
  const [customCases, setCustomCases] = useState<CustomTestCase[]>([]);
  const [showAddDrawer, setShowAddDrawer] = useState<boolean>(false);

  // Filter state for results matrix
  const [statusFilter, setStatusFilter] = useState<"ALL" | "PASSED" | "FAILED" | "ABSTAINED">("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Form fields for + Custom Test
  const [name, setName] = useState("");
  const [query, setQuery] = useState("");
  const [policy, setPolicy] = useState<PolicyMode>("strict");
  const [expectedVerdict, setExpectedVerdict] = useState<"APPROVE" | "ABSTAIN" | "QUALIFY" | "ESCALATE">("APPROVE");
  const [category, setCategory] = useState("CUSTOM_SCENARIO");
  const [refDate, setRefDate] = useState<string>(new Date().toISOString().slice(0, 10));

  // Load custom tests from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem("veritas_custom_benchmarks");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) setCustomCases(parsed);
      }
    } catch {}
  }, []);

  const saveCustomCases = (cases: CustomTestCase[]) => {
    setCustomCases(cases);
    try {
      localStorage.setItem("veritas_custom_benchmarks", JSON.stringify(cases));
    } catch {}
  };

  const handleAddCustomCase = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !query.trim()) return;

    const newCase: CustomTestCase = {
      case_id: `CUSTOM-${String(customCases.length + 1).padStart(2, "0")}`,
      name: name.trim(),
      query: query.trim(),
      policy,
      expected_verdict: expectedVerdict,
      category: category.trim() || "CUSTOM_SCENARIO",
      ref_date: refDate || new Date().toISOString().slice(0, 10),
      test_goal: "User-defined live regulatory compliance scenario",
    };

    saveCustomCases([...customCases, newCase]);
    setName("");
    setQuery("");
    setShowAddDrawer(false);
  };

  const handleApplyPreset = (preset: (typeof STANDARD_PRESETS)[0]) => {
    setName(preset.name);
    setCategory(preset.category);
    setQuery(preset.query);
    setPolicy(preset.policy);
    setExpectedVerdict(preset.expected_verdict);
  };

  const handleRemoveCustomCase = (caseId: string) => {
    saveCustomCases(customCases.filter((c) => c.case_id !== caseId));
  };

  const handleClearResults = () => {
    setReport(null);
    setError(null);
    setExpandedCaseId(null);
  };

  const runBenchmark = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch("/api/benchmark/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ custom_cases: customCases }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || `Benchmark execution failed with status ${res.status}`);
      } else {
        const data: BenchmarkSuiteReport = await res.json();
        setReport(data);
        if (data.cases.length > 0) {
          setExpandedCaseId(data.cases[0].case_id);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to execute benchmark suite");
    } finally {
      setRunning(false);
    }
  };

  const exportReportJson = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mnb_veritas_benchmark_${report.suite_id}_${report.executed_at}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Filtered cases for the matrix
  const filteredCases = useMemo(() => {
    if (!report) return [];
    return report.cases.filter((c) => {
      if (statusFilter === "PASSED" && !c.passed) return false;
      if (statusFilter === "FAILED" && c.passed) return false;
      if (statusFilter === "ABSTAINED" && c.actual_verdict !== "ABSTAIN") return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          c.name.toLowerCase().includes(q) ||
          c.case_id.toLowerCase().includes(q) ||
          c.query.toLowerCase().includes(q) ||
          c.category.toLowerCase().includes(q) ||
          (c.audit_id && c.audit_id.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [report, statusFilter, searchQuery]);

  const passedCount = report?.cases.filter((c) => c.passed).length ?? 0;
  const failedCount = report ? report.cases.length - passedCount : 0;
  const abstainedCount = report?.cases.filter((c) => c.actual_verdict === "ABSTAIN").length ?? 0;

  return (
    <div className="space-y-4 font-sans text-zinc-100">
      {/* 1. Streamlined Action Bar Header */}
      <div className="rounded-xl border border-[#27272A] bg-[#111114] p-4 space-y-3 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono text-xs">
                <Activity className="h-3 w-3" />
              </span>
              <h2 className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-200">
                Institutional Forensic Benchmark Lab
              </h2>
              <span className="rounded border border-cyan-800/60 bg-cyan-950/40 px-2 py-0.5 font-mono text-[10px] font-semibold text-cyan-300">
                5-POINT INVARIANT SUITE {customCases.length > 0 ? `+ ${customCases.length} CUSTOM` : ""}
              </span>
            </div>
            <p className="text-xs text-zinc-400 font-sans">
              Ground-truth adversarial stress battery evaluating continuous quote matching, lakh/crore scale, FY reconciliation, and zero-hallucination deterrence.
            </p>
          </div>

          {/* Action Buttons Group */}
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            {report && (
              <>
                <button
                  type="button"
                  onClick={handleClearResults}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#27272A] bg-[#18181B] px-3 py-1.5 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  <span>Clear Results</span>
                </button>
                <button
                  type="button"
                  onClick={exportReportJson}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#27272A] bg-[#18181B] px-3 py-1.5 text-zinc-300 hover:text-emerald-400 hover:border-emerald-800/60 transition"
                >
                  <Download className="h-3.5 w-3.5" />
                  <span>Export JSON</span>
                </button>
              </>
            )}

            <button
              type="button"
              onClick={() => setShowAddDrawer((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-800/60 bg-emerald-950/40 px-3 py-1.5 text-emerald-300 hover:bg-emerald-900/50 hover:text-emerald-200 transition font-semibold"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>{showAddDrawer ? "Close Builder" : "+ Custom Test"}</span>
            </button>

            <button
              type="button"
              onClick={runBenchmark}
              disabled={running}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-1.5 font-bold uppercase tracking-wider text-zinc-950 transition hover:bg-emerald-400 disabled:opacity-50 shadow-sm"
            >
              <Play className={`h-3.5 w-3.5 fill-current ${running ? "animate-spin" : ""}`} />
              <span>{running ? "EVALUATING BATTERY..." : `RUN BENCHMARK (${5 + customCases.length})`}</span>
            </button>
          </div>
        </div>

        {/* Invariant Coverage Badges */}
        <div className="flex flex-wrap items-center gap-1.5 font-mono text-[10px] text-zinc-500 border-t border-[#27272A] pt-2.5">
          <span className="uppercase text-zinc-500 mr-1">Invariants Tested:</span>
          <span className="rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-zinc-300">
            1. NO PARAPHRASE QUOTE
          </span>
          <span className="rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-zinc-300">
            2. LAKH / CRORE SCALE
          </span>
          <span className="rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-zinc-300">
            3. FY BOUNDARY CONCORD
          </span>
          <span className="rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-zinc-300">
            4. CROSS-LAB INDEPENDENCE
          </span>
          <span className="rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-zinc-300">
            5. TEMPORAL EXPIRATION
          </span>
        </div>

        {/* 2. Custom Scenario Builder Drawer */}
        {showAddDrawer && (
          <form
            onSubmit={handleAddCustomCase}
            className="rounded-lg border border-emerald-700/50 bg-[#0C1014] p-4 space-y-3 font-mono text-xs animate-in fade-in duration-150"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#27272A] pb-2">
              <span className="font-bold text-emerald-400 uppercase tracking-wide flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5" />
                Add Enterprise Compliance Custom Scenario
              </span>
              <div className="flex items-center gap-1 text-[10px] text-zinc-400">
                <span className="text-zinc-500">Presets:</span>
                {STANDARD_PRESETS.slice(0, 3).map((p) => (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => handleApplyPreset(p)}
                    className="rounded border border-[#27272A] bg-[#18181B] px-1.5 py-0.5 text-zinc-300 hover:text-emerald-300 hover:border-emerald-800 transition"
                  >
                    {p.name.split(" ")[0]}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1 sm:col-span-2">
                <label className="text-[10px] uppercase text-zinc-400 block font-semibold">
                  Scenario Title
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. SEBI Mutual Fund Liquid Buffer Mandate"
                  className="w-full rounded border border-[#27272A] bg-[#141416] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase text-zinc-400 block font-semibold">
                  Category Tag
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full rounded border border-[#27272A] bg-[#141416] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
                >
                  <option value="CUSTOM_SCENARIO">CUSTOM_SCENARIO</option>
                  <option value="STATUTORY_MANDATE">STATUTORY_MANDATE</option>
                  <option value="SCALE_DISTORTION">SCALE_DISTORTION</option>
                  <option value="REGULATORY_RULE">REGULATORY_RULE</option>
                  <option value="TEMPORAL_CHECK">TEMPORAL_CHECK</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1">
                <label className="text-[10px] uppercase text-zinc-400 block font-semibold">
                  Policy Mode
                </label>
                <select
                  value={policy}
                  onChange={(e) => setPolicy(e.target.value as PolicyMode)}
                  className="w-full rounded border border-[#27272A] bg-[#141416] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
                >
                  <option value="strict">strict (Zero Hallucination)</option>
                  <option value="balanced">balanced (Standard Invariant)</option>
                  <option value="standard">standard (Baseline)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase text-zinc-400 block font-semibold">
                  Expected Verdict
                </label>
                <select
                  value={expectedVerdict}
                  onChange={(e) =>
                    setExpectedVerdict(e.target.value as "APPROVE" | "ABSTAIN" | "QUALIFY" | "ESCALATE")
                  }
                  className="w-full rounded border border-[#27272A] bg-[#141416] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
                >
                  <option value="APPROVE">APPROVE (Verified Against Truth)</option>
                  <option value="ABSTAIN">ABSTAIN (Ungrounded / Distorted Trap)</option>
                  <option value="QUALIFY">QUALIFY (Partial Grounding)</option>
                  <option value="ESCALATE">ESCALATE (Human Compliance Signoff)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase text-zinc-400 block font-semibold">
                  Reference Date
                </label>
                <input
                  type="date"
                  value={refDate}
                  onChange={(e) => setRefDate(e.target.value)}
                  className="w-full rounded border border-[#27272A] bg-[#141416] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] uppercase text-zinc-400 block font-semibold">
                Regulatory Claim / Prompt to Verify
              </label>
              <textarea
                required
                rows={2}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter regulatory assertion or factual prompt to test against live truth chunks..."
                className="w-full rounded border border-[#27272A] bg-[#141416] p-2.5 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none font-sans"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-1 border-t border-[#27272A]">
              <button
                type="button"
                onClick={() => setShowAddDrawer(false)}
                className="rounded border border-[#27272A] bg-[#18181B] px-3 py-1 text-zinc-400 hover:text-zinc-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded bg-emerald-500 px-4 py-1 font-bold text-zinc-950 hover:bg-emerald-400 transition"
              >
                Save Custom Scenario
              </button>
            </div>
          </form>
        )}

        {/* Active Custom Tests Shelf */}
        {customCases.length > 0 && (
          <div className="rounded-lg border border-[#27272A] bg-[#0E1013] p-3 space-y-2 font-mono text-xs">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 border-b border-[#27272A] pb-1.5">
              <span className="font-semibold text-zinc-300">
                ACTIVE CUSTOM ENTERPRISE SCENARIOS ({customCases.length})
              </span>
              <span className="text-zinc-500 text-[10px]">Persisted Locally in Workstation</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {customCases.map((c) => (
                <div
                  key={c.case_id}
                  className="flex items-center justify-between rounded border border-[#27272A] bg-[#141416] p-2.5 gap-2"
                >
                  <div className="space-y-0.5 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-semibold text-zinc-200 text-xs truncate">{c.name}</span>
                      <span className="rounded bg-[#1F1F23] px-1.5 py-0.2 text-[9px] text-emerald-400 font-semibold">
                        EXP: {c.expected_verdict}
                      </span>
                      <span className="rounded bg-[#1F1F23] px-1.5 py-0.2 text-[9px] text-zinc-400">
                        {c.policy}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-500 font-sans truncate">{c.query}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveCustomCase(c.case_id)}
                    title="Remove custom scenario"
                    className="inline-flex h-6 w-6 items-center justify-center rounded text-zinc-500 hover:text-rose-400 hover:bg-rose-950/30 transition shrink-0"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-rose-800/80 bg-rose-950/40 p-3 font-mono text-xs text-rose-300 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* 3. High-Density Results Matrix (When Evaluated) */}
      {report ? (
        <div className="space-y-4">
          {/* Top Scorecard Strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-xs">
            <div className="rounded-xl border border-[#27272A] bg-[#111114] p-3.5 space-y-1">
              <span className="text-[10px] uppercase text-zinc-500 font-semibold block">ACCURACY SCORE</span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-emerald-400">{report.accuracy_pct}%</span>
                <span className="text-[11px] text-zinc-500">
                  ({report.passed_cases}/{report.total_cases})
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-[#27272A] bg-[#111114] p-3.5 space-y-1">
              <span className="text-[10px] uppercase text-zinc-500 font-semibold block">HALLUCINATION CATCH</span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-emerald-400">{report.hallucination_catch_rate_pct}%</span>
                <span className="text-[11px] text-zinc-500">Strict Veto</span>
              </div>
            </div>

            <div className="rounded-xl border border-[#27272A] bg-[#111114] p-3.5 space-y-1">
              <span className="text-[10px] uppercase text-zinc-500 font-semibold block">AVG PIPELINE TIME</span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-zinc-200">{report.avg_latency_ms}</span>
                <span className="text-[11px] text-zinc-500">ms / query</span>
              </div>
            </div>

            <div className="rounded-xl border border-[#27272A] bg-[#111114] p-3.5 space-y-1">
              <span className="text-[10px] uppercase text-zinc-500 font-semibold block">TOTAL COMPUTED COST</span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-zinc-200">
                  ${(report.total_estimated_cost_usd ?? 0).toFixed(4)}
                </span>
                <span className="text-[11px] text-zinc-500">USD</span>
              </div>
            </div>
          </div>

          {/* Matrix Filter Strip */}
          <div className="flex flex-wrap items-center justify-between gap-3 font-mono text-xs">
            <div className="flex items-center gap-1 rounded-lg border border-[#27272A] bg-[#111114] p-1">
              {(["ALL", "PASSED", "FAILED", "ABSTAINED"] as const).map((mode) => {
                const count =
                  mode === "ALL"
                    ? report.cases.length
                    : mode === "PASSED"
                    ? passedCount
                    : mode === "FAILED"
                    ? failedCount
                    : abstainedCount;
                const active = statusFilter === mode;
                return (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setStatusFilter(mode)}
                    className={`rounded px-2.5 py-1 text-[11px] transition font-semibold ${
                      active
                        ? "bg-[#18181B] text-zinc-100 border border-[#27272A]"
                        : "text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    {mode} ({count})
                  </button>
                );
              })}
            </div>

            <div className="relative min-w-[240px]">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter scenarios, queries, or audit IDs..."
                className="w-full rounded-lg border border-[#27272A] bg-[#111114] py-1.5 pl-8 pr-3 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Forensic Results Table */}
          <div className="rounded-xl border border-[#27272A] bg-[#111114] overflow-hidden shadow-sm font-mono text-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[#27272A] bg-[#141416] text-[10px] text-zinc-400 uppercase tracking-wider">
                    <th className="py-2.5 px-3">OUTCOME</th>
                    <th className="py-2.5 px-3">CASE ID &amp; TITLE</th>
                    <th className="py-2.5 px-3">INVARIANT GATES</th>
                    <th className="py-2.5 px-3">TELEMETRY</th>
                    <th className="py-2.5 px-3">AUDIT RECORD</th>
                    <th className="py-2.5 px-3 text-right">DETAILS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#27272A]">
                  {filteredCases.map((c) => {
                    const isExpanded = expandedCaseId === c.case_id;
                    const passed = c.passed;
                    return (
                      <React.Fragment key={c.case_id}>
                        <tr
                          onClick={() => setExpandedCaseId(isExpanded ? null : c.case_id)}
                          className={`cursor-pointer transition-colors ${
                            isExpanded ? "bg-[#18181B]/80" : "hover:bg-[#141416]/50"
                          }`}
                        >
                          {/* Col 1: Outcome & Verdict Match */}
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <span
                                className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold border ${
                                  passed
                                    ? "bg-emerald-950/70 border-emerald-800/60 text-emerald-400"
                                    : "bg-rose-950/70 border-rose-800/60 text-rose-300"
                                }`}
                              >
                                {passed ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                                <span>{passed ? "PASS" : "FAIL"}</span>
                              </span>
                              <div className="text-[10px] text-zinc-400 space-y-0.5">
                                <span className="block text-zinc-500">Exp: {c.expected_verdict}</span>
                                <span className={
                                  c.actual_verdict === "APPROVE"
                                    ? "text-emerald-400 font-semibold"
                                    : c.actual_verdict === "ABSTAIN"
                                    ? "text-rose-400 font-semibold"
                                    : "text-amber-400 font-semibold"
                                }>
                                  Got: {c.actual_verdict}
                                </span>
                              </div>
                            </div>
                          </td>

                          {/* Col 2: Case ID & Title */}
                          <td className="py-2.5 px-3">
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="font-bold text-zinc-200">{c.case_id}</span>
                                <span className="rounded border border-[#27272A] bg-[#18181B] px-1.5 py-0.2 text-[9px] text-zinc-400">
                                  {c.category}
                                </span>
                              </div>
                              <div className="text-zinc-200 font-sans text-xs font-medium truncate max-w-sm">
                                {c.name}
                              </div>
                            </div>
                          </td>

                          {/* Col 3: Invariant Gates Badges */}
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            <div className="flex items-center gap-1 text-[9px] font-semibold">
                              <span
                                title="No Paraphrase Exact Quote Match"
                                className={`rounded px-1.5 py-0.5 border ${
                                  c.quote_verified
                                    ? "border-emerald-800/60 bg-emerald-950/50 text-emerald-300"
                                    : "border-zinc-800 bg-zinc-900/60 text-zinc-500"
                                }`}
                              >
                                Quote
                              </span>
                              <span
                                title="Lakh vs Crore Scale Concord"
                                className={`rounded px-1.5 py-0.5 border ${
                                  c.scale_check_passed !== false
                                    ? "border-emerald-800/60 bg-emerald-950/50 text-emerald-300"
                                    : "border-rose-800/60 bg-rose-950/50 text-rose-300"
                                }`}
                              >
                                Scale
                              </span>
                              <span
                                title="Financial Year Boundary Check"
                                className={`rounded px-1.5 py-0.5 border ${
                                  c.fy_check_passed !== false
                                    ? "border-emerald-800/60 bg-emerald-950/50 text-emerald-300"
                                    : "border-rose-800/60 bg-rose-950/50 text-rose-300"
                                }`}
                              >
                                FY
                              </span>
                              <span
                                title="Cross-Lab Auditor Independence"
                                className={`rounded px-1.5 py-0.5 border ${
                                  c.cross_lab_passed
                                    ? "border-emerald-800/60 bg-emerald-950/50 text-emerald-300"
                                    : "border-zinc-800 bg-zinc-900/60 text-zinc-500"
                                }`}
                              >
                                Cross-Lab
                              </span>
                            </div>
                          </td>

                          {/* Col 4: Telemetry */}
                          <td className="py-2.5 px-3 whitespace-nowrap text-[11px] text-zinc-400">
                            <div>{c.latency_ms}ms</div>
                            <div className="text-[10px] text-zinc-500">
                              ${(c.estimated_cost_usd ?? 0).toFixed(4)}
                            </div>
                          </td>

                          {/* Col 5: Cryptographic Audit ID */}
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            {c.audit_id ? (
                              <a
                                href={`/api/audits/${c.audit_id}/certificate?format=json`}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-[10px] text-cyan-400 hover:border-cyan-700/60 hover:text-cyan-300 transition"
                              >
                                <FileCode className="h-2.5 w-2.5" />
                                <span>{c.audit_id}</span>
                              </a>
                            ) : (
                              <span className="text-[10px] text-zinc-600">IN-MEMORY</span>
                            )}
                          </td>

                          {/* Col 6: Expand Arrow */}
                          <td className="py-2.5 px-3 text-right">
                            {isExpanded ? (
                              <ChevronDown className="h-4 w-4 text-zinc-400 ml-auto" />
                            ) : (
                              <ChevronRight className="h-4 w-4 text-zinc-600 ml-auto" />
                            )}
                          </td>
                        </tr>

                        {/* Expandable Forensic Inspection Drawer */}
                        {isExpanded && (
                          <tr className="bg-[#0C0E11] border-b border-[#27272A]">
                            <td colSpan={6} className="p-4 space-y-3 font-sans text-xs">
                              <div className="space-y-1">
                                <span className="font-mono text-[10px] uppercase text-zinc-500 block font-semibold">
                                  ASSERTION QUERY TESTED
                                </span>
                                <p className="font-mono text-xs text-zinc-200 bg-[#141416] p-2.5 rounded border border-[#27272A]">
                                  &quot;{c.query}&quot;
                                </p>
                              </div>

                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {/* Synthesis output */}
                                <div className="space-y-1">
                                  <span className="font-mono text-[10px] uppercase text-zinc-500 block font-semibold">
                                    SYNTHESIS PREVIEW &amp; DETAILS
                                  </span>
                                  <div className="rounded border border-[#27272A] bg-[#141416] p-2.5 space-y-1 font-mono text-[11px]">
                                    <div className="text-zinc-300">&quot;{c.answer_preview}&quot;</div>
                                    <div className="text-[10px] text-zinc-500 pt-1 border-t border-[#27272A]">
                                      {c.details}
                                    </div>
                                  </div>
                                </div>

                                {/* Extracted verbatim quote */}
                                <div className="space-y-1">
                                  <span className="font-mono text-[10px] uppercase text-zinc-500 block font-semibold">
                                    VERBATIM TRUTH CITATION / REASONS
                                  </span>
                                  <div className="rounded border border-[#27272A] bg-[#141416] p-2.5 space-y-1 font-mono text-[11px]">
                                    {c.verbatim_quotes && c.verbatim_quotes.length > 0 ? (
                                      <div className="text-emerald-300">
                                        &quot;{c.verbatim_quotes[0]}&quot;
                                      </div>
                                    ) : c.rejection_reasons && c.rejection_reasons.length > 0 ? (
                                      <div className="text-rose-400">
                                        {c.rejection_reasons.join(" · ")}
                                      </div>
                                    ) : (
                                      <div className="text-zinc-500">
                                        Strict abstention triggered. Zero ungrounded assertions certified.
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>

                              {/* Forensic Audit Row Footer with Certificate Actions */}
                              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#27272A] font-mono text-[11px] text-zinc-400">
                                <div className="flex items-center gap-3">
                                  <span>Policy: <strong className="text-zinc-200">{c.policy.toUpperCase()}</strong></span>
                                  <span>Claims Audited: <strong className="text-zinc-200">{c.claims_verified}</strong></span>
                                  <span>
                                    Tokens: <strong className="text-zinc-200">{c.prompt_tokens ?? 0} in / {c.completion_tokens ?? 0} out</strong>
                                  </span>
                                </div>

                                {c.audit_id && (
                                  <div className="flex items-center gap-2">
                                    <a
                                      href={`/api/audits/${c.audit_id}/certificate?format=pdf`}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-2.5 py-1 text-emerald-400 hover:border-emerald-700/60 hover:text-emerald-300 transition text-[10px]"
                                    >
                                      <FileText className="h-3 w-3" />
                                      <span>Export PDF Certificate</span>
                                    </a>
                                    <a
                                      href={`/api/audits/${c.audit_id}/certificate?format=json`}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-2.5 py-1 text-cyan-400 hover:border-cyan-700/60 hover:text-cyan-300 transition text-[10px]"
                                    >
                                      <FileCode className="h-3 w-3" />
                                      <span>Export JSON Seal</span>
                                    </a>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* 4. Pre-Flight Manifest (Standby State - Clean & High Density) */
        <div className="rounded-xl border border-[#27272A] bg-[#111114] p-5 space-y-4 shadow-sm font-mono text-xs">
          <div className="flex items-center justify-between border-b border-[#27272A] pb-3">
            <span className="font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
              <Terminal className="h-4 w-4 text-emerald-400" />
              Pre-Flight Forensic Invariant Battery Manifest ({5 + customCases.length} Scenarios Queued)
            </span>
            <span className="rounded border border-emerald-900/60 bg-emerald-950/30 px-2 py-0.5 text-emerald-400 text-[10px] font-semibold">
              READY TO EXECUTE
            </span>
          </div>

          <div className="divide-y divide-[#27272A]">
            <div className="py-2.5 flex items-center justify-between text-zinc-400 text-[11px]">
              <span className="font-bold text-zinc-200">1. BENCH-01 · Green Hydrogen Mission Outlay (FY 2025-26)</span>
              <span className="rounded bg-emerald-950/60 border border-emerald-800/50 px-2 py-0.5 text-[10px] text-emerald-400 font-semibold">
                EXP: APPROVE (₹4,850 Cr)
              </span>
            </div>
            <div className="py-2.5 flex items-center justify-between text-zinc-400 text-[11px]">
              <span className="font-bold text-zinc-200">2. BENCH-02 · Offshore African LNG Sovereign Guarantee Trap</span>
              <span className="rounded bg-rose-950/60 border border-rose-800/50 px-2 py-0.5 text-[10px] text-rose-300 font-semibold">
                EXP: ABSTAIN (Zero Evidence)
              </span>
            </div>
            <div className="py-2.5 flex items-center justify-between text-zinc-400 text-[11px]">
              <span className="font-bold text-zinc-200">3. BENCH-03 · 100x Scale Distortion Trap (Lakh vs Crore)</span>
              <span className="rounded bg-rose-950/60 border border-rose-800/50 px-2 py-0.5 text-[10px] text-rose-300 font-semibold">
                EXP: ABSTAIN (Magnitude Discord)
              </span>
            </div>
            <div className="py-2.5 flex items-center justify-between text-zinc-400 text-[11px]">
              <span className="font-bold text-zinc-200">4. BENCH-04 · SEBI AIF Statutory Liquid Cushion Mandate</span>
              <span className="rounded bg-emerald-950/60 border border-emerald-800/50 px-2 py-0.5 text-[10px] text-emerald-400 font-semibold">
                EXP: APPROVE (10% Buffer)
              </span>
            </div>
            <div className="py-2.5 flex items-center justify-between text-zinc-400 text-[11px]">
              <span className="font-bold text-zinc-200">5. BENCH-05 · Temporal Expiration Boundary Enforcement</span>
              <span className="rounded bg-rose-950/60 border border-rose-800/50 px-2 py-0.5 text-[10px] text-rose-300 font-semibold">
                EXP: ABSTAIN (Evaluated June 2028)
              </span>
            </div>

            {customCases.map((c, i) => (
              <div key={c.case_id} className="py-2.5 flex items-center justify-between text-zinc-400 text-[11px]">
                <span className="font-bold text-cyan-300">
                  {5 + i + 1}. {c.case_id} · {c.name}
                </span>
                <span className="rounded bg-cyan-950/60 border border-cyan-800/50 px-2 py-0.5 text-[10px] text-cyan-300 font-semibold">
                  EXP: {c.expected_verdict} ({c.policy})
                </span>
              </div>
            ))}
          </div>

          <div className="rounded border border-[#27272A] bg-[#09090B] p-3 text-[11px] text-zinc-400 flex items-center justify-between">
            <span>Click &quot;RUN BENCHMARK&quot; in the header to evaluate all scenarios against live pipeline stages.</span>
            <span className="text-emerald-400 font-semibold">Zero Synthetic Telemetry</span>
          </div>
        </div>
      )}
    </div>
  );
}
