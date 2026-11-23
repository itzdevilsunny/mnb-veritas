"use client";

import React, { useEffect, useState } from "react";

interface BenchmarkCaseResult {
  case_id: string;
  name: string;
  category: string;
  query: string;
  policy: string;
  expected_verdict: string;
  actual_verdict: string;
  passed: boolean;
  latency_ms: number;
  claims_verified: number;
  details: string;
  answer_preview: string;
}

interface BenchmarkSuiteReport {
  suite_id: string;
  executed_at: string;
  total_cases: number;
  passed_cases: number;
  accuracy_pct: number;
  hallucination_catch_rate_pct: number;
  avg_latency_ms: number;
  total_estimated_cost_usd: number;
  cases: BenchmarkCaseResult[];
}

interface CustomTestCase {
  case_id: string;
  name: string;
  query: string;
  policy: string;
  ref_date: string;
  expected_verdict: string;
  category: string;
  test_goal: string;
}

export default function BenchmarkRunner() {
  const [report, setReport] = useState<BenchmarkSuiteReport | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCase, setSelectedCase] = useState<string | null>(null);

  // Custom enterprise benchmark state
  const [customCases, setCustomCases] = useState<CustomTestCase[]>([]);
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newCaseName, setNewCaseName] = useState("");
  const [newCaseQuery, setNewCaseQuery] = useState("");
  const [newCaseVerdict, setNewCaseVerdict] = useState("APPROVE");
  const [newCasePolicy, setNewCasePolicy] = useState("strict");
  const [newCaseCategory, setNewCaseCategory] = useState("ENTERPRISE_CUSTOM");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("veritas_custom_benchmarks");
      if (saved) {
        setCustomCases(JSON.parse(saved));
      }
    } catch {
      // Ignored
    }
  }, []);

  const handleAddCustomCase = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCaseName.trim() || !newCaseQuery.trim()) return;
    const newCase: CustomTestCase = {
      case_id: `CUSTOM-0${customCases.length + 1}`,
      name: newCaseName.trim(),
      query: newCaseQuery.trim(),
      expected_verdict: newCaseVerdict,
      policy: newCasePolicy,
      category: newCaseCategory,
      ref_date: new Date().toISOString().slice(0, 10),
      test_goal: "Custom user-defined regulatory compliance scenario",
    };
    const updated = [...customCases, newCase];
    setCustomCases(updated);
    try {
      localStorage.setItem("veritas_custom_benchmarks", JSON.stringify(updated));
    } catch {}
    setNewCaseName("");
    setNewCaseQuery("");
    setShowAddModal(false);
  };

  const handleRemoveCustomCase = (caseId: string) => {
    const updated = customCases.filter((c) => c.case_id !== caseId);
    setCustomCases(updated);
    try {
      localStorage.setItem("veritas_custom_benchmarks", JSON.stringify(updated));
    } catch {}
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
        const data = await res.json();
        setReport(data);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to run benchmark");
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

  return (
    <div className="space-y-6">
      {/* Benchmark Header Banner */}
      <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-emerald-500/20 text-emerald-400 font-mono text-xs">
              🧪
            </span>
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-200">
              Institutional Forensic Benchmark Lab
            </span>
            <span className="rounded bg-sky-950/70 border border-sky-800/60 px-2 py-0.5 font-mono text-[10px] text-sky-400">
              5-Point Stress Battery
            </span>
          </div>

          <div className="flex items-center gap-3">
            {report && (
              <button
                type="button"
                onClick={exportReportJson}
                className="font-mono text-xs text-zinc-400 hover:text-zinc-200 border border-zinc-800 bg-zinc-900/60 rounded px-2.5 py-1 transition"
              >
                Export Certificate (.JSON)
              </button>
            )}
            <button
              type="button"
              onClick={() => setShowAddModal(!showAddModal)}
              className="font-mono text-xs text-emerald-400 hover:text-emerald-300 border border-emerald-800/60 bg-emerald-950/40 rounded px-2.5 py-1 transition"
            >
              {showAddModal ? "Cancel" : "+ Custom Test"}
            </button>
            <button
              type="button"
              onClick={runBenchmark}
              disabled={running}
              className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-4 py-1.5 font-mono text-xs font-bold uppercase tracking-wider text-zinc-950 transition hover:bg-emerald-400 disabled:opacity-50"
            >
              <span>⚡</span>
              <span>{running ? "RUNNING BATTERY..." : `RUN BENCHMARK (${5 + customCases.length})`}</span>
            </button>
          </div>
        </div>

        <p className="text-xs text-zinc-400 leading-relaxed">
          Standardized automated stress-testing battery executing five institutional scenarios plus user-defined custom compliance rules.
        </p>

        {/* Custom Scenario Builder Modal / Form */}
        {showAddModal && (
          <form
            onSubmit={handleAddCustomCase}
            className="rounded-lg border border-emerald-500/40 bg-[#0B0F12] p-4 space-y-3 font-mono text-xs"
          >
            <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
              <span className="font-bold text-emerald-300 uppercase">
                Add Enterprise Compliance Test Case
              </span>
              <span className="text-[10px] text-zinc-500">Evaluated in S1-S5 Pipeline</span>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-[10px] uppercase text-zinc-400">Scenario Title</label>
                <input
                  type="text"
                  required
                  value={newCaseName}
                  onChange={(e) => setNewCaseName(e.target.value)}
                  placeholder="e.g. Daily Settlement Velocity Guardrail"
                  className="w-full rounded border border-zinc-800 bg-[#080C0E] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-[10px] uppercase text-zinc-400">Expected Verdict</label>
                  <select
                    value={newCaseVerdict}
                    onChange={(e) => setNewCaseVerdict(e.target.value)}
                    className="w-full rounded border border-zinc-800 bg-[#080C0E] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
                  >
                    <option value="APPROVE">APPROVE (Valid Fact)</option>
                    <option value="ABSTAIN">ABSTAIN (Trap / Reject)</option>
                    <option value="QUALIFY">QUALIFY (Caveat)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] uppercase text-zinc-400">Policy Mode</label>
                  <select
                    value={newCasePolicy}
                    onChange={(e) => setNewCasePolicy(e.target.value)}
                    className="w-full rounded border border-zinc-800 bg-[#080C0E] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none"
                  >
                    <option value="strict">Strict</option>
                    <option value="balanced">Balanced</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] uppercase text-zinc-400">Query Claim to Verify</label>
              <textarea
                required
                rows={2}
                value={newCaseQuery}
                onChange={(e) => setNewCaseQuery(e.target.value)}
                placeholder="Enter regulatory question or assertion to test..."
                className="w-full rounded border border-zinc-800 bg-[#080C0E] p-2 text-xs text-zinc-200 focus:border-emerald-500 focus:outline-none font-sans"
              />
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="rounded border border-zinc-800 px-3 py-1 text-zinc-400 hover:text-zinc-200 text-xs"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded bg-emerald-500 px-3 py-1 font-bold text-zinc-950 hover:bg-emerald-400 text-xs"
              >
                Save Custom Scenario
              </button>
            </div>
          </form>
        )}

        {/* Custom Scenarios List */}
        {customCases.length > 0 && (
          <div className="rounded-lg border border-zinc-800/80 bg-[#080C0E] p-3 space-y-2 font-mono text-xs">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 border-b border-zinc-800/80 pb-1">
              <span>ACTIVE CUSTOM ENTERPRISE SCENARIOS ({customCases.length})</span>
              <span className="text-zinc-500">Persisted Locally</span>
            </div>
            <div className="space-y-1.5">
              {customCases.map((c) => (
                <div
                  key={c.case_id}
                  className="flex items-center justify-between rounded border border-zinc-800 bg-zinc-900/40 p-2"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-zinc-200">{c.name}</span>
                      <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
                        Exp: {c.expected_verdict}
                      </span>
                    </div>
                    <div className="text-[11px] text-zinc-500 font-sans truncate max-w-md">
                      {c.query}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveCustomCase(c.case_id)}
                    className="text-rose-400 hover:text-rose-300 text-xs px-2 py-0.5"
                  >
                    ✕ Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-rose-800/80 bg-rose-950/40 p-3 font-mono text-xs text-rose-300">
            {error}
          </div>
        )}
      </div>

      {/* Results Scorecard */}
      {report && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-4">
              <span className="block font-mono text-[10px] uppercase text-zinc-500">
                Accuracy Score
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-mono text-2xl font-bold text-emerald-400">
                  {report.accuracy_pct}%
                </span>
                <span className="font-mono text-xs text-zinc-500">
                  ({report.passed_cases}/{report.total_cases})
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-4">
              <span className="block font-mono text-[10px] uppercase text-zinc-500">
                Hallucination Catch
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-mono text-2xl font-bold text-emerald-400">
                  {report.hallucination_catch_rate_pct}%
                </span>
                <span className="font-mono text-xs text-zinc-500">
                  Strict Abstention
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-4">
              <span className="block font-mono text-[10px] uppercase text-zinc-500">
                Avg Latency
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-mono text-2xl font-bold text-zinc-200">
                  {report.avg_latency_ms}
                </span>
                <span className="font-mono text-xs text-zinc-500">ms / query</span>
              </div>
            </div>

            <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-4">
              <span className="block font-mono text-[10px] uppercase text-zinc-500">
                Battery Compute Cost
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-mono text-2xl font-bold text-zinc-200">
                  ${report.total_estimated_cost_usd}
                </span>
                <span className="font-mono text-xs text-zinc-500">USD</span>
              </div>
            </div>
          </div>

          {/* Test Battery Breakdown */}
          <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
              <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300">
                Execution Matrix &amp; Invariant Verification
              </span>
              <span className="font-mono text-[11px] text-zinc-500">
                SUITE_ID: {report.suite_id}
              </span>
            </div>

            <div className="divide-y divide-zinc-800/60">
              {report.cases.map((testCase) => {
                const isSelected = selectedCase === testCase.case_id;
                return (
                  <div
                    key={testCase.case_id}
                    onClick={() =>
                      setSelectedCase(isSelected ? null : testCase.case_id)
                    }
                    className="cursor-pointer py-3.5 space-y-2 transition hover:bg-[#121820]/60 px-2 rounded-lg"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2 font-mono text-xs">
                        <span className="font-bold text-zinc-300">
                          {testCase.case_id}
                        </span>
                        <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-400">
                          {testCase.category}
                        </span>
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                            testCase.passed
                              ? "bg-emerald-950/80 text-emerald-300 border border-emerald-800/60"
                              : "bg-rose-950/80 text-rose-300 border border-rose-800/60"
                          }`}
                        >
                          {testCase.passed ? "PASSED" : "FAILED"}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 font-mono text-xs">
                        <span className="text-zinc-500">
                          Expected:{" "}
                          <span className="text-zinc-300">
                            {testCase.expected_verdict}
                          </span>
                        </span>
                        <span className="text-zinc-500">
                          Got:{" "}
                          <span
                            className={
                              testCase.actual_verdict === "APPROVE"
                                ? "text-emerald-400 font-bold"
                                : testCase.actual_verdict === "QUALIFY"
                                ? "text-amber-400 font-bold"
                                : "text-rose-400 font-bold"
                            }
                          >
                            {testCase.actual_verdict}
                          </span>
                        </span>
                        <span className="text-[11px] text-zinc-500">
                          {testCase.latency_ms}ms
                        </span>
                      </div>
                    </div>

                    <div className="text-xs text-zinc-200 font-medium">
                      {testCase.name}
                    </div>

                    <p className="font-mono text-[11px] text-zinc-400">
                      Query: &quot;{testCase.query}&quot;
                    </p>

                    {isSelected && (
                      <div className="mt-2 space-y-2 rounded-lg border border-zinc-800 bg-[#0B0F12] p-3 font-mono text-xs">
                        <div className="text-[11px] text-zinc-300">
                          <span className="text-zinc-500">Outcome Details:</span>{" "}
                          {testCase.details}
                        </div>
                        <div className="text-[11px] text-zinc-400">
                          <span className="text-zinc-500">Synthesis:</span> &quot;
                          {testCase.answer_preview}&quot;
                        </div>
                        <div className="text-[10px] text-zinc-500">
                          Claims Audited: {testCase.claims_verified} | Policy:{" "}
                          {testCase.policy.toUpperCase()}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Empty State Prompt */}
      {!report && !running && (
        <div className="rounded-xl border border-dashed border-zinc-800 bg-[#0B0F12] p-10 text-center space-y-3">
          <div className="text-3xl">🎯</div>
          <h4 className="font-mono text-xs font-semibold uppercase text-zinc-300">
            Ready for Automated Evaluation
          </h4>
          <p className="mx-auto max-w-md text-xs text-zinc-500">
            Click &quot;Run Benchmark Suite&quot; to evaluate MNB Veritas against the standardized regulatory test cases. Generates live accuracy, hallucination deterrence, and latency telemetry.
          </p>
          <button
            type="button"
            onClick={runBenchmark}
            className="rounded-lg bg-emerald-500 px-4 py-2 font-mono text-xs font-bold uppercase text-zinc-950 hover:bg-emerald-400 transition"
          >
            Start 5-Point Benchmark Battery
          </button>
        </div>
      )}
    </div>
  );
}
