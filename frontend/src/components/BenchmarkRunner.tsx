"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
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
  Terminal,
  Trash2,
  XCircle,
} from "lucide-react";
import type {
  BenchmarkCaseResult,
  BenchmarkSuiteReport,
  CustomTestCase,
  ManagedSource,
  PolicyMode,
} from "@/types/veritas";

interface StandardScenario {
  case_id: string;
  name: string;
  category: string;
  query: string;
  policy: PolicyMode;
  ref_date: string;
  expected_verdict: "APPROVE" | "ABSTAIN" | "QUALIFY" | "ESCALATE";
  expected_label: string;
  invariant_tested: string;
  target_corpus_id?: string;
  is_adversarial_trap?: boolean;
}

const STANDARD_SCENARIOS: StandardScenario[] = [
  {
    case_id: "BENCH-01",
    name: "Green Hydrogen Mission Outlay (FY 2025-26)",
    category: "GROUNDED_FACT",
    query: "What is the financial outlay for the National Green Hydrogen Mission for FY 2025-26?",
    policy: "strict",
    ref_date: "2025-03-31",
    expected_verdict: "APPROVE",
    expected_label: "EXP: APPROVE (₹4,850 Cr)",
    invariant_tested: "NO PARAPHRASE QUOTE",
    target_corpus_id: "doc_green_hydrogen_2024",
    is_adversarial_trap: false,
  },
  {
    case_id: "BENCH-02",
    name: "Offshore African LNG Sovereign Guarantee Trap",
    category: "HALLUCINATION_TRAP",
    query: "Explain India's current bilateral sovereign guarantee commitments for offshore African LNG terminal construction in FY 2025-26.",
    policy: "strict",
    ref_date: "2025-03-31",
    expected_verdict: "ABSTAIN",
    expected_label: "EXP: ABSTAIN (Zero Evidence)",
    invariant_tested: "CROSS-LAB INDEPENDENCE",
    target_corpus_id: undefined,
    is_adversarial_trap: true,
  },
  {
    case_id: "BENCH-03",
    name: "100x Scale Distortion Trap (Lakh vs Crore)",
    category: "SCALE_DISTORTION",
    query: "The approved budgetary allocation for the National Green Hydrogen Mission for FY 2025-26 was ₹4,85,000 Lakh Crore.",
    policy: "strict",
    ref_date: "2025-03-31",
    expected_verdict: "ABSTAIN",
    expected_label: "EXP: ABSTAIN (Magnitude Discord)",
    invariant_tested: "LAKH / CRORE SCALE",
    target_corpus_id: "doc_green_hydrogen_2024",
    is_adversarial_trap: true,
  },
  {
    case_id: "BENCH-04",
    name: "SEBI AIF Statutory Liquid Cushion Mandate",
    category: "STATUTORY_MANDATE",
    query: "What is the minimum percentage of unencumbered liquid assets that Alternative Investment Funds must maintain under emergency drawdown rules?",
    policy: "strict",
    ref_date: "2025-01-15",
    expected_verdict: "APPROVE",
    expected_label: "EXP: APPROVE (10% Buffer)",
    invariant_tested: "STATUTORY EXTRACTION",
    target_corpus_id: "doc_budget_2025",
    is_adversarial_trap: false,
  },
  {
    case_id: "BENCH-05",
    name: "Temporal Expiration Boundary Enforcement",
    category: "TEMPORAL_ISOLATION",
    query: "What is the budgetary allocation for the National Green Hydrogen Mission for FY 2025-26 evaluated in June 2028?",
    policy: "strict",
    ref_date: "2028-06-01",
    expected_verdict: "ABSTAIN",
    expected_label: "EXP: ABSTAIN (Evaluated June 2028)",
    invariant_tested: "TEMPORAL EXPIRY",
    target_corpus_id: "doc_green_hydrogen_2024",
    is_adversarial_trap: true,
  },
];

const PRESET_CUSTOM_RULES = [
  {
    name: "SEBI BRSR Core ESG Footprint Assurance",
    category: "STATUTORY_MANDATE",
    query: "What percentage of value chain footprints must obtain reasonable assurance under SEBI BRSR Core?",
    policy: "strict" as PolicyMode,
    expected_verdict: "APPROVE" as const,
    ref_date: "2025-03-31",
    test_goal: "Validates regulatory circular quote extraction and mandated value-chain ESG assurance.",
  },
  {
    name: "RBI Digital Account Velocity Thresholds",
    category: "REGULATORY_RULE",
    query: "What are the cooling-off transaction limits for newly provisioned digital accounts under RBI master directions?",
    policy: "strict" as PolicyMode,
    expected_verdict: "APPROVE" as const,
    ref_date: "2025-03-31",
    test_goal: "Enforces quantitative limit reconciliation against master digital banking security circulars.",
  },
  {
    name: "Adversarial 100x Scale Inflation Trap",
    category: "SCALE_DISTORTION",
    query: "The cabinet approved ₹4,85,000 Lakh Crore for the Green Hydrogen Mission outlay instead of ₹4,850 Crore.",
    policy: "strict" as PolicyMode,
    expected_verdict: "ABSTAIN" as const,
    ref_date: "2025-03-31",
    test_goal: "Enforces pure-Python lakh vs crore scale discord trap rejection.",
  },
  {
    name: "Offshore Sovereign Collateral Probe",
    category: "HALLUCINATION_TRAP",
    query: "Explain India's bilateral sovereign counter-guarantees for East African LNG infrastructure projects.",
    policy: "strict" as PolicyMode,
    expected_verdict: "ABSTAIN" as const,
    ref_date: "2025-03-31",
    test_goal: "Enforces strict abstention on ungrounded claims with zero evidence in gazettes.",
  },
];

export default function BenchmarkRunner() {
  const [report, setReport] = useState<BenchmarkSuiteReport | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);

  // Active sources from live backend for corpus awareness
  const [sources, setSources] = useState<ManagedSource[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState<boolean>(true);

  // Custom test suite state (persisted in localStorage)
  const [customCases, setCustomCases] = useState<CustomTestCase[]>([]);
  const [showAddDrawer, setShowAddDrawer] = useState<boolean>(false);

  // Filter state for results matrix
  const [statusFilter, setStatusFilter] = useState<"ALL" | "PASSED" | "FAILED" | "ABSTAINED">("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Form fields for Custom Test Rule Builder
  const [name, setName] = useState("");
  const [query, setQuery] = useState("");
  const [policy, setPolicy] = useState<PolicyMode>("strict");
  const [expectedVerdict, setExpectedVerdict] = useState<"APPROVE" | "ABSTAIN" | "QUALIFY" | "ESCALATE">("APPROVE");
  const [category, setCategory] = useState("STATUTORY_MANDATE");
  const [refDate, setRefDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [isSeedingCorpus, setIsSeedingCorpus] = useState(false);

  // Missing required corpuses for the 5-point benchmark battery
  const missingRequiredCorpuses = useMemo(() => {
    const REQUIRED = ["doc_green_hydrogen_2024", "doc_budget_2025"];
    return REQUIRED.filter(
      (id) => !sources.some((s) => s.doc_id === id && s.is_active !== false)
    );
  }, [sources]);

  // Handle seeding benchmark truth corpuses
  const handleSeedCorpus = async () => {
    setIsSeedingCorpus(true);
    try {
      const res = await fetch("/api/benchmark/seed-corpus", { method: "POST" });
      if (res.ok) {
        await fetchSources();
      }
    } catch (err) {
      console.error("Failed to seed benchmark corpus:", err);
    } finally {
      setIsSeedingCorpus(false);
    }
  };

  // Load sources from live backend
  const fetchSources = async () => {
    setSourcesLoading(true);
    try {
      const res = await fetch("/api/sources", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setSources(Array.isArray(data) ? data : []);
      }
    } catch {
      // Non-fatal
    } finally {
      setSourcesLoading(false);
    }
  };

  useEffect(() => {
    void fetchSources();
  }, []);

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

  const handleApplyPreset = (preset: (typeof PRESET_CUSTOM_RULES)[0]) => {
    setName(preset.name);
    setCategory(preset.category);
    setQuery(preset.query);
    setPolicy(preset.policy);
    setExpectedVerdict(preset.expected_verdict);
    setRefDate(preset.ref_date);
  };

  const handleRemoveCustomCase = (caseId: string) => {
    saveCustomCases(customCases.filter((c) => c.case_id !== caseId));
  };

  const handleClearResults = () => {
    setReport(null);
    setError(null);
    setExpandedCaseId(null);
  };

  const totalScenarios = STANDARD_SCENARIOS.length + customCases.length;

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

  // Helper to check corpus match
  const getCorpusStatus = (scenario: StandardScenario) => {
    if (scenario.is_adversarial_trap && !scenario.target_corpus_id) {
      return {
        label: "CORPUS: UNGROUNDED TRAP (ADVERSARIAL)",
        className: "border-rose-900/60 bg-rose-950/40 text-rose-300",
      };
    }
    if (scenario.target_corpus_id) {
      const isLoaded = sources.some((s) => s.doc_id === scenario.target_corpus_id && s.is_active !== false);
      if (isLoaded) {
        return {
          label: `CORPUS: ${scenario.target_corpus_id} (ACTIVE)`,
          className: "border-emerald-900/50 bg-emerald-950/30 text-emerald-300",
        };
      }
      return {
        label: `CORPUS: ${scenario.target_corpus_id} (UNAVAILABLE)`,
        className: "border-amber-900/60 bg-amber-950/40 text-amber-300",
      };
    }
    return {
      label: `CORPUS: ${sources.length} ACTIVE TRUTH SOURCES`,
      className: "border-[#27272A] bg-[#141416] text-zinc-400",
    };
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

  return (
    <div className="space-y-4 font-sans text-zinc-100">
      {/* 1. Header Toolbar */}
      <div className="rounded-lg border border-[#27272A] bg-[#111114] p-4 space-y-3 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded border border-emerald-800/60 bg-emerald-950/40 text-emerald-400">
                <Activity className="h-3 w-3" />
              </span>
              <h2 className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-200">
                INSTITUTIONAL FORENSIC BENCHMARK LAB
              </h2>
              <span className="rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 font-mono text-[10px] text-zinc-300">
                5-POINT INVARIANT SUITE {customCases.length > 0 ? `+ ${customCases.length} CUSTOM` : ""}
              </span>
            </div>
            <p className="text-xs text-zinc-400 font-sans">
              Ground-truth adversarial stress battery evaluating continuous quote matching, lakh/crore scale, FY reconciliation, and zero-hallucination deterrence.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            {report && (
              <>
                <button
                  type="button"
                  onClick={handleClearResults}
                  className="inline-flex items-center gap-1.5 rounded border border-[#27272A] bg-[#18181B] px-3 py-1.5 font-semibold text-zinc-300 hover:text-zinc-100 hover:border-zinc-600 transition"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  <span>Clear Results</span>
                </button>
                <button
                  type="button"
                  onClick={exportReportJson}
                  className="inline-flex items-center gap-1.5 rounded border border-[#27272A] bg-[#18181B] px-3 py-1.5 font-semibold text-zinc-300 hover:text-zinc-100 hover:border-zinc-600 transition"
                >
                  <Download className="h-3.5 w-3.5" />
                  <span>Export JSON</span>
                </button>
              </>
            )}

            {/* Custom Test Button */}
            <button
              type="button"
              onClick={() => setShowAddDrawer((v) => !v)}
              className={`inline-flex items-center gap-1.5 rounded border px-3 py-1.5 font-semibold transition ${
                showAddDrawer
                  ? "border-emerald-600/70 bg-emerald-950/60 text-emerald-300"
                  : "border-[#27272A] bg-[#18181B] text-zinc-200 hover:border-zinc-600 hover:bg-[#1f1f23]"
              }`}
            >
              <Plus className="h-3.5 w-3.5" />
              <span>{showAddDrawer ? "Close Builder" : "Custom Test"}</span>
            </button>

            {/* Primary Run Benchmark Button (Restrained Forensic Aesthetic) */}
            <button
              type="button"
              onClick={runBenchmark}
              disabled={running}
              className="inline-flex items-center gap-2 rounded border border-emerald-600/70 bg-emerald-950/50 hover:bg-emerald-900/60 text-emerald-300 font-mono text-xs font-semibold px-4 py-1.5 shadow-sm transition disabled:opacity-50"
            >
              <Play className={`h-3 w-3 fill-current ${running ? "animate-spin" : ""}`} />
              <span>{running ? "EVALUATING BATTERY..." : `RUN BENCHMARK (${totalScenarios})`}</span>
            </button>
          </div>
        </div>

        {/* Invariant Tags Header */}
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

        {/* 2. Custom Rule Builder Form Drawer */}
        {showAddDrawer && (
          <form
            onSubmit={handleAddCustomCase}
            className="rounded-lg border border-[#27272A] bg-[#0E1013] p-4 space-y-3 font-mono text-xs shadow-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#27272A] pb-2.5">
              <span className="font-semibold text-zinc-200 uppercase tracking-wide flex items-center gap-1.5">
                <FileCode className="h-3.5 w-3.5 text-emerald-400" />
                CREATE CUSTOM AUDIT SCENARIO
              </span>
              <div className="flex flex-wrap items-center gap-1 text-[10px]">
                <span className="text-zinc-500 mr-1">Load Preset:</span>
                {PRESET_CUSTOM_RULES.map((p) => (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => handleApplyPreset(p)}
                    className="rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-zinc-300 hover:text-emerald-300 hover:border-emerald-800/60 transition"
                  >
                    {p.name.split(" ")[0]}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1 sm:col-span-2">
                <label className="text-[10px] uppercase text-zinc-400 block font-semibold">
                  Rule Name / Title
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. SEBI Mutual Fund Liquid Buffer Mandate"
                  className="w-full rounded border border-[#27272A] bg-[#141416] px-2.5 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-emerald-500/80 focus:outline-none transition font-sans"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase text-zinc-400 block font-semibold">
                  Category Tag
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full rounded border border-[#27272A] bg-[#141416] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none transition"
                >
                  <option value="STATUTORY_MANDATE">STATUTORY_MANDATE</option>
                  <option value="REGULATORY_RULE">REGULATORY_RULE</option>
                  <option value="SCALE_DISTORTION">SCALE_DISTORTION</option>
                  <option value="HALLUCINATION_TRAP">HALLUCINATION_TRAP</option>
                  <option value="TEMPORAL_CHECK">TEMPORAL_CHECK</option>
                  <option value="CUSTOM_SCENARIO">CUSTOM_SCENARIO</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1">
                <label className="text-[10px] uppercase text-zinc-400 block font-semibold">
                  Verification Policy Mode
                </label>
                <select
                  value={policy}
                  onChange={(e) => setPolicy(e.target.value as PolicyMode)}
                  className="w-full rounded border border-[#27272A] bg-[#141416] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none transition"
                >
                  <option value="strict">STRICT (Zero Hallucination)</option>
                  <option value="balanced">BALANCED (Scale & FY Concord)</option>
                  <option value="standard">STANDARD (Baseline)</option>
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
                  className="w-full rounded border border-[#27272A] bg-[#141416] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none transition"
                >
                  <option value="APPROVE">APPROVE (Grounded in Truth)</option>
                  <option value="ABSTAIN">ABSTAIN (Ungrounded / Distorted)</option>
                  <option value="QUALIFY">QUALIFY (Qualified Caveat)</option>
                  <option value="ESCALATE">ESCALATE (Human Signoff)</option>
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
                  className="w-full rounded border border-[#27272A] bg-[#141416] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none transition"
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
                placeholder="Enter regulatory assertion or factual prompt to test against live truth sources..."
                className="w-full rounded border border-[#27272A] bg-[#141416] p-2.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-emerald-500/80 focus:outline-none transition font-sans"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#27272A]">
              <button
                type="button"
                onClick={() => setShowAddDrawer(false)}
                className="rounded border border-[#27272A] bg-[#18181B] px-3 py-1 text-zinc-400 hover:text-zinc-200 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded border border-emerald-700/60 bg-emerald-950/60 px-4 py-1 font-semibold text-emerald-300 hover:bg-emerald-900/60 transition"
              >
                Save Custom Scenario
              </button>
            </div>
          </form>
        )}

        {missingRequiredCorpuses.length > 0 && (
          <div className="rounded-lg border border-amber-900/60 bg-amber-950/30 p-3 font-mono text-xs text-amber-300 flex flex-wrap items-center justify-between gap-3 shadow-sm">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
              <span>
                Benchmark Ground Truth Corpuses missing ({missingRequiredCorpuses.join(", ")}). Grounded cases will abstain until indexed.
              </span>
            </div>
            <button
              type="button"
              onClick={handleSeedCorpus}
              disabled={isSeedingCorpus}
              className="inline-flex items-center gap-1.5 rounded border border-amber-700/60 bg-amber-900/40 px-3 py-1 font-semibold text-amber-200 hover:bg-amber-800/50 transition disabled:opacity-50"
            >
              <Database className="h-3.5 w-3.5" />
              <span>{isSeedingCorpus ? "Indexing Truth Documents..." : "Seed Benchmark Ground Truth"}</span>
            </button>
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
            <div className="rounded-lg border border-[#27272A] bg-[#111114] p-3.5 space-y-1">
              <span className="text-[10px] uppercase text-zinc-500 font-semibold block">
                ACCURACY SCORE
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-emerald-400 tabular-nums">{report.accuracy_pct}%</span>
                <span className="text-[11px] text-zinc-500 tabular-nums">
                  ({report.passed_cases}/{report.total_cases})
                </span>
              </div>
            </div>

            <div className="rounded-lg border border-[#27272A] bg-[#111114] p-3.5 space-y-1">
              <span className="text-[10px] uppercase text-zinc-500 font-semibold block">
                HALLUCINATION CATCH
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-emerald-400 tabular-nums">
                  {report.hallucination_catch_rate_pct}%
                </span>
                <span className="text-[11px] text-zinc-500">Strict Veto</span>
              </div>
            </div>

            <div className="rounded-lg border border-[#27272A] bg-[#111114] p-3.5 space-y-1">
              <span className="text-[10px] uppercase text-zinc-500 font-semibold block">
                AVG PIPELINE TIME
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-zinc-200 tabular-nums">
                  {report.avg_latency_ms}ms
                </span>
                <span className="text-[11px] text-zinc-500">Across Battery</span>
              </div>
            </div>

            <div className="rounded-lg border border-[#27272A] bg-[#111114] p-3.5 space-y-1">
              <span className="text-[10px] uppercase text-zinc-500 font-semibold block">
                TOTAL TELEMETRY COST
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-zinc-200 tabular-nums">
                  ${report.total_estimated_cost_usd.toFixed(4)}
                </span>
                <span className="text-[11px] text-zinc-500">Real Spend</span>
              </div>
            </div>
          </div>

          {/* Results Table Card */}
          <div className="rounded-lg border border-[#27272A] bg-[#111114] p-4 space-y-3.5 shadow-sm font-mono text-xs">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#27272A] pb-3">
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                {(["ALL", "PASSED", "FAILED", "ABSTAINED"] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setStatusFilter(tab)}
                    className={`rounded px-2.5 py-1 font-semibold uppercase tracking-wider text-[11px] transition ${
                      statusFilter === tab
                        ? "bg-[#18181B] text-zinc-100 border border-[#27272A] shadow-sm"
                        : "text-zinc-500 hover:text-zinc-300 hover:bg-[#141416]"
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-500 pointer-events-none" />
                  <input
                    type="text"
                    placeholder="Search results..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-48 sm:w-60 rounded border border-[#27272A] bg-[#09090B] py-1.5 pl-8 pr-2.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-emerald-500/80 focus:outline-none transition font-sans"
                  />
                </div>
              </div>
            </div>

            {/* Matrix Table */}
            <div className="overflow-x-auto rounded border border-[#27272A]">
              <table className="w-full text-left font-mono text-xs">
                <thead className="border-b border-[#27272A] bg-[#0C0E11] text-[10px] uppercase text-zinc-500 tracking-wider">
                  <tr>
                    <th className="py-2 px-3">Status</th>
                    <th className="py-2 px-3">Scenario &amp; Policy</th>
                    <th className="py-2 px-3">Invariants Verified</th>
                    <th className="py-2 px-3">Verdict (Exp → Act)</th>
                    <th className="py-2 px-3">Latency / Cost</th>
                    <th className="py-2 px-3">Audit Proof</th>
                    <th className="py-2 px-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#27272A] bg-[#111114]">
                  {filteredCases.map((c) => {
                    const isExpanded = expandedCaseId === c.case_id;
                    return (
                      <React.Fragment key={c.case_id}>
                        <tr
                          onClick={() => setExpandedCaseId(isExpanded ? null : c.case_id)}
                          className="hover:bg-[#14161A] cursor-pointer transition select-none"
                        >
                          {/* Col 1: Status */}
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            <span
                              className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                                c.passed
                                  ? "bg-emerald-950/80 text-emerald-300 border border-emerald-800/60"
                                  : "bg-rose-950/80 text-rose-300 border border-rose-800/60"
                              }`}
                            >
                              {c.passed ? (
                                <CheckCircle2 className="h-3 w-3" />
                              ) : (
                                <XCircle className="h-3 w-3" />
                              )}
                              <span>{c.passed ? "PASS" : "MISMATCH"}</span>
                            </span>
                          </td>

                          {/* Col 2: Scenario & Policy */}
                          <td className="py-2.5 px-3 min-w-[200px]">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-semibold text-zinc-200 text-xs">
                                {c.case_id} · {c.name}
                              </span>
                              <span className="rounded border border-[#27272A] bg-[#18181B] px-1.5 py-0.2 text-[9px] text-zinc-400 uppercase">
                                {c.policy}
                              </span>
                            </div>
                            <div className="text-[11px] text-zinc-500 font-sans truncate max-w-sm pt-0.5">
                              {c.query}
                            </div>
                          </td>

                          {/* Col 3: Invariant Gate Indicators */}
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            <div className="flex items-center gap-1 text-[9px]">
                              <span
                                className={`rounded px-1.5 py-0.5 border ${
                                  c.quote_verified
                                    ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/50"
                                    : "bg-zinc-900 text-zinc-500 border-zinc-800"
                                }`}
                                title="Character-for-character quote verified"
                              >
                                Quote
                              </span>
                              <span
                                className={`rounded px-1.5 py-0.5 border ${
                                  c.scale_check_passed
                                    ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/50"
                                    : "bg-rose-950/60 text-rose-300 border-rose-800/50"
                                }`}
                                title="Lakh vs Crore scale concord"
                              >
                                Scale
                              </span>
                              <span
                                className={`rounded px-1.5 py-0.5 border ${
                                  c.fy_check_passed
                                    ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/50"
                                    : "bg-rose-950/60 text-rose-300 border-rose-800/50"
                                }`}
                                title="FY boundary alignment"
                              >
                                FY
                              </span>
                              <span
                                className={`rounded px-1.5 py-0.5 border ${
                                  c.cross_lab_passed
                                    ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/50"
                                    : "bg-zinc-900 text-zinc-500 border-zinc-800"
                                }`}
                                title="Cross-lab auditor independence"
                              >
                                Cross-Lab
                              </span>
                            </div>
                          </td>

                          {/* Col 4: Verdict Exp -> Act */}
                          <td className="py-2.5 px-3 whitespace-nowrap font-mono text-[11px]">
                            <div className="flex items-center gap-1.5">
                              <span className="text-zinc-400">{c.expected_verdict}</span>
                              <ArrowRight className="h-2.5 w-2.5 text-zinc-600" />
                              <span
                                className={`font-semibold ${
                                  c.actual_verdict === "APPROVE"
                                    ? "text-emerald-400"
                                    : c.actual_verdict === "QUALIFY"
                                    ? "text-amber-400"
                                    : "text-rose-400"
                                }`}
                              >
                                {c.actual_verdict}
                              </span>
                            </div>
                          </td>

                          {/* Col 5: Latency / Cost */}
                          <td className="py-2.5 px-3 whitespace-nowrap text-zinc-400 tabular-nums">
                            <div>{c.latency_ms}ms</div>
                            <div className="text-[10px] text-zinc-500">
                              ${(c.estimated_cost_usd ?? 0).toFixed(4)}
                            </div>
                          </td>

                          {/* Col 6: Cryptographic Audit ID */}
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            {c.audit_id ? (
                              <a
                                href={`/api/audits/${c.audit_id}/certificate?format=json`}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-1.5 py-0.5 text-[10px] text-zinc-300 hover:text-emerald-300 transition"
                              >
                                <FileCode className="h-2.5 w-2.5 text-emerald-400" />
                                <span>{c.audit_id}</span>
                              </a>
                            ) : (
                              <span className="text-[10px] text-zinc-600">IN-MEMORY</span>
                            )}
                          </td>

                          {/* Col 7: Expand Arrow */}
                          <td className="py-2.5 px-3 text-right">
                            {isExpanded ? (
                              <ChevronDown className="h-4 w-4 text-zinc-400 ml-auto" />
                            ) : (
                              <ChevronRight className="h-4 w-4 text-zinc-600 ml-auto" />
                            )}
                          </td>
                        </tr>

                        {/* Expandable Forensic Details Drawer */}
                        {isExpanded && (
                          <tr className="bg-[#0C0E11] border-b border-[#27272A]">
                            <td colSpan={7} className="p-4 space-y-3 font-sans text-xs">
                              <div className="space-y-1">
                                <span className="font-mono text-[10px] uppercase text-zinc-500 block">
                                  ASSERTION QUERY TESTED
                                </span>
                                <p className="font-mono text-xs text-zinc-200 bg-[#141416] p-2.5 rounded border border-[#27272A]">
                                  &ldquo;{c.query}&rdquo;
                                </p>
                              </div>

                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {/* Synthesis output */}
                                <div className="space-y-1">
                                  <span className="font-mono text-[10px] uppercase text-zinc-500 block">
                                    SYNTHESIS PREVIEW &amp; DETAILS
                                  </span>
                                  <div className="rounded border border-[#27272A] bg-[#141416] p-2.5 text-xs space-y-1">
                                    <div className="text-zinc-300">&ldquo;{c.answer_preview}&rdquo;</div>
                                    <div className="text-[10px] text-zinc-500 pt-1 border-t border-[#27272A]">
                                      {c.details}
                                    </div>
                                  </div>
                                </div>

                                {/* Extracted verbatim quote */}
                                <div className="space-y-1">
                                  <span className="font-mono text-[10px] uppercase text-zinc-500 block">
                                    VERBATIM TRUTH CITATION / REASONS
                                  </span>
                                  <div className="rounded border border-[#27272A] bg-[#141416] p-2.5 text-xs">
                                    {c.verbatim_quotes && c.verbatim_quotes.length > 0 ? (
                                      <div className="text-emerald-300 font-mono text-[11px]">
                                        &ldquo;{c.verbatim_quotes[0]}&rdquo;
                                      </div>
                                    ) : c.rejection_reasons && c.rejection_reasons.length > 0 ? (
                                      <div className="text-rose-400 font-mono text-[11px]">
                                        {c.rejection_reasons.join(" · ")}
                                      </div>
                                    ) : (
                                      <div className="text-zinc-500 font-mono text-[11px]">
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
                                    Tokens: <strong className="text-zinc-200">{c.prompt_tokens ?? 0} / {c.completion_tokens ?? 0}</strong>
                                  </span>
                                </div>

                                {c.audit_id && (
                                  <div className="flex items-center gap-2">
                                    <a
                                      href={`/api/audits/${c.audit_id}/certificate?format=pdf`}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="inline-flex items-center gap-1 rounded border border-emerald-800/60 bg-emerald-950/40 px-2.5 py-1 text-emerald-300 hover:bg-emerald-900/60 transition"
                                    >
                                      <FileText className="h-3 w-3" />
                                      <span>Export PDF Certificate</span>
                                    </a>
                                    <a
                                      href={`/api/audits/${c.audit_id}/certificate?format=json`}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#18181B] px-2.5 py-1 text-zinc-300 hover:text-zinc-100 transition"
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
        /* 4. Pre-Flight Manifest (Standby State - Dynamic Queue & Corpus Grounding) */
        <div className="rounded-lg border border-[#27272A] bg-[#111114] p-5 space-y-4 shadow-sm font-mono text-xs">
          <div className="flex items-center justify-between border-b border-[#27272A] pb-3">
            <span className="font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
              <Terminal className="h-4 w-4 text-emerald-400" />
              Pre-Flight Forensic Invariant Battery Manifest ({totalScenarios} Scenarios Queued)
            </span>
            <span className="rounded border border-emerald-900/60 bg-emerald-950/30 px-2 py-0.5 text-emerald-400 text-[10px] font-semibold">
              READY TO EXECUTE
            </span>
          </div>

          <div className="divide-y divide-[#27272A]">
            {/* Standard 5 Scenarios with Live Corpus Grounding */}
            {STANDARD_SCENARIOS.map((scenario, index) => {
              const corpusStatus = getCorpusStatus(scenario);
              const isApprove = scenario.expected_verdict === "APPROVE";

              return (
                <div
                  key={scenario.case_id}
                  className="py-3 flex flex-wrap items-center justify-between gap-2 text-zinc-300 text-xs font-sans transition hover:bg-[#141417] px-1 rounded"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono font-bold text-zinc-100">
                        {index + 1}. {scenario.case_id}
                      </span>
                      <span className="font-semibold text-zinc-200">
                        {scenario.name}
                      </span>
                      {/* Policy Mode Badge */}
                      <span className="rounded border border-[#27272A] bg-[#18181B] px-1.5 py-0.2 font-mono text-[10px] font-semibold text-zinc-400 uppercase">
                        {scenario.policy}
                      </span>
                      {/* Invariant Tag */}
                      <span className="rounded border border-[#27272A] bg-[#09090B] px-1.5 py-0.2 font-mono text-[9px] text-zinc-500 uppercase">
                        {scenario.invariant_tested}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
                      {/* Corpus Grounding Indicator */}
                      <span
                        className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.2 text-[9px] font-semibold uppercase ${corpusStatus.className}`}
                      >
                        <Database className="h-2.5 w-2.5" />
                        <span>{corpusStatus.label}</span>
                      </span>
                      <span className="text-zinc-600">·</span>
                      <span className="text-zinc-500 truncate max-w-md font-sans">
                        &ldquo;{scenario.query}&rdquo;
                      </span>
                    </div>
                  </div>

                  {/* Expected Verdict Badge */}
                  <div className="font-mono text-right shrink-0">
                    <span
                      className={`rounded px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider border ${
                        isApprove
                          ? "bg-emerald-950/70 border-emerald-800/60 text-emerald-300"
                          : "bg-rose-950/70 border-rose-800/60 text-rose-300"
                      }`}
                    >
                      {scenario.expected_label}
                    </span>
                  </div>
                </div>
              );
            })}

            {/* User Custom Scenarios in Manifest */}
            {customCases.map((c, i) => (
              <div
                key={c.case_id}
                className="py-3 flex flex-wrap items-center justify-between gap-2 text-zinc-300 text-xs font-sans transition hover:bg-[#141417] px-1 rounded"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono font-bold text-cyan-400">
                      {STANDARD_SCENARIOS.length + i + 1}. {c.case_id}
                    </span>
                    <span className="font-semibold text-zinc-200">
                      {c.name}
                    </span>
                    {/* Policy Mode Badge */}
                    <span className="rounded border border-[#27272A] bg-[#18181B] px-1.5 py-0.2 font-mono text-[10px] font-semibold text-zinc-400 uppercase">
                      {c.policy}
                    </span>
                    {/* Category Tag */}
                    <span className="rounded border border-[#27272A] bg-[#09090B] px-1.5 py-0.2 font-mono text-[9px] text-cyan-400 uppercase">
                      {c.category}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
                    <span className="inline-flex items-center gap-1 rounded border border-[#27272A] bg-[#141416] px-1.5 py-0.2 text-[9px] text-zinc-400 font-semibold uppercase">
                      <Database className="h-2.5 w-2.5 text-cyan-400" />
                      <span>CORPUS: {sources.length} ACTIVE TRUTH SOURCES</span>
                    </span>
                    <span className="text-zinc-600">·</span>
                    <span className="text-zinc-500 truncate max-w-md font-sans">
                      &ldquo;{c.query}&rdquo;
                    </span>
                  </div>
                </div>

                {/* Expected Verdict Badge & Remove Action */}
                <div className="flex items-center gap-2 font-mono shrink-0">
                  <span className="rounded border border-cyan-800/60 bg-cyan-950/60 px-2.5 py-1 text-[10px] font-bold text-cyan-300 uppercase tracking-wider">
                    EXP: {c.expected_verdict} ({c.policy})
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemoveCustomCase(c.case_id)}
                    title="Remove custom rule from queue"
                    className="inline-flex h-6 w-6 items-center justify-center rounded text-zinc-500 hover:text-rose-400 hover:bg-rose-950/40 transition"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Restrained Institutional Status Strip */}
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#27272A] bg-[#09090B] px-3.5 py-2 font-mono text-[11px] text-zinc-400">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span className="font-semibold text-zinc-300">QUEUE READY</span>
              <span className="text-zinc-600">·</span>
              <span className="tabular-nums">{totalScenarios} SCENARIOS IN QUEUE</span>
              <span className="text-zinc-600">·</span>
              <span className="text-zinc-500">DETERMINISTIC CODE GATES ARMED</span>
            </div>
            <span className="text-zinc-400 text-[10px] uppercase tracking-wider font-semibold">
              100% LIVE PIPELINE EXECUTION · ZERO SYNTHETIC TELEMETRY
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
