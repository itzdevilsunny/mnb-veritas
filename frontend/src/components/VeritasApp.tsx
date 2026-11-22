"use client";

import React, { useCallback, useEffect, useState } from "react";
import AuditWorkbench from "@/components/AuditWorkbench";
import VeritasPlayground from "@/components/VeritasPlayground";
import SourceManager from "@/components/SourceManager";
import AuditLogsView from "@/components/AuditLogsView";
import type { ManagedSource } from "@/types/veritas";

type TabId = "workbench" | "playground" | "sources" | "audits";

interface CircuitState {
  state: "CLOSED" | "OPEN" | "HALF_OPEN";
  failure_count: number;
  success_count: number;
}

export default function VeritasApp() {
  const [activeTab, setActiveTab] = useState<TabId>("workbench");
  const [sourceCount, setSourceCount] = useState<number>(4);
  const [auditSyncKey, setAuditSyncKey] = useState<number>(0);
  const [sourceSyncKey, setSourceSyncKey] = useState<number>(0);
  const [providerCircuits, setProviderCircuits] = useState<Record<string, CircuitState>>({});
  const [redisConnected, setRedisConnected] = useState<boolean>(false);
  const [circuitsLoading, setCircuitsLoading] = useState<boolean>(false);

  const fetchProviderHealth = useCallback(async () => {
    try {
      setCircuitsLoading(true);
      const res = await fetch("/api/health/providers", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setProviderCircuits(data.providers || data);
        setRedisConnected(Boolean(data.redis_connected));
      }
    } catch {
      // Backend may be warming up
    } finally {
      setCircuitsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProviderHealth();
  }, [fetchProviderHealth]);

  const handleResetCircuit = async (lab: string) => {
    try {
      const res = await fetch(`/api/health/providers/${lab}/reset`, { method: "POST" });
      if (res.ok) {
        await fetchProviderHealth();
      }
    } catch (e) {
      console.error("Failed to reset circuit for", lab, e);
    }
  };

  const handleVerificationComplete = useCallback(() => {
    setAuditSyncKey((prev) => prev + 1);
    fetchProviderHealth();
  }, [fetchProviderHealth]);

  const handleSourcesUpdated = useCallback((sources: ManagedSource[]) => {
    setSourceCount(sources.length);
  }, []);

  const handleGlobalRefresh = () => {
    setAuditSyncKey((prev) => prev + 1);
    setSourceSyncKey((prev) => prev + 1);
    fetchProviderHealth();
  };

  const labList = [
    { key: "anthropic", label: "Claude" },
    { key: "openai", label: "OpenAI" },
    { key: "google", label: "Gemini" },
    { key: "xai", label: "Grok" },
  ];

  const totalOpenOrHalf = Object.values(providerCircuits).filter(
    (c) => c.state === "OPEN" || c.state === "HALF_OPEN"
  ).length;

  return (
    <div
      suppressHydrationWarning
      className="mx-auto min-h-screen max-w-5xl px-4 py-6 space-y-6"
    >
      {/* Top Banner & Engine Status */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800/80 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-emerald-500/20 text-emerald-400 font-mono font-bold text-xs border border-emerald-500/40">
            V
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold tracking-tight text-zinc-100">
                MNB VERITAS
              </span>
              <span className="rounded bg-emerald-950 px-1.5 py-0.2 font-mono text-[10px] font-semibold text-emerald-400 border border-emerald-800/60">
                v1.4
              </span>
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">
              Evidence Engine
            </div>
          </div>
        </div>

        {/* Engine System Status Indicator & Multi-Lab Circuit Breakers */}
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <div className="flex items-center gap-1.5 rounded-md border border-zinc-800 bg-[#0E1318] px-2.5 py-1 text-zinc-400">
            <span>{redisConnected ? "REDIS" : "IN-MEMORY"}</span>
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                redisConnected ? "bg-emerald-400" : "bg-cyan-400"
              }`}
            ></span>
          </div>

          {/* Provider Circuit Pills */}
          <div className="flex items-center gap-1.5 rounded-md border border-zinc-800 bg-[#0E1318] px-2 py-1 text-[11px]">
            {labList.map((lab) => {
              const info = providerCircuits[lab.key];
              const st = info ? info.state : "CLOSED";
              const isClosed = st === "CLOSED";
              const isHalf = st === "HALF_OPEN";
              return (
                <div key={lab.key} className="flex items-center gap-1 px-1">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      isClosed
                        ? "bg-emerald-400"
                        : isHalf
                        ? "bg-amber-400 animate-pulse"
                        : "bg-red-500 animate-pulse"
                    }`}
                  />
                  <span className={isClosed ? "text-zinc-300" : isHalf ? "text-amber-300 font-semibold" : "text-red-400 font-bold"}>
                    {lab.label}
                  </span>
                  {!isClosed && (
                    <button
                      type="button"
                      onClick={() => handleResetCircuit(lab.key)}
                      title={`Reset ${lab.label} circuit breaker`}
                      className="ml-0.5 rounded px-1 text-[9px] bg-red-950 text-red-300 hover:bg-red-900 border border-red-800/60"
                    >
                      reset
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          <div
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] ${
              totalOpenOrHalf > 0
                ? "border-amber-800/50 bg-amber-950/40 text-amber-300"
                : "border-zinc-800 bg-[#0E1318] text-emerald-400"
            }`}
          >
            <span>CIRCUITS</span>
            <span className="font-bold">
              {totalOpenOrHalf > 0 ? `${totalOpenOrHalf} TRIPPED` : "ALL HEALTHY"}
            </span>
          </div>

          <button
            type="button"
            onClick={handleGlobalRefresh}
            title="Refresh system state"
            disabled={circuitsLoading}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-zinc-800 bg-[#0E1318] text-zinc-400 hover:text-zinc-200 transition active:scale-95"
          >
            ↻
          </button>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="flex items-center gap-6 border-b border-zinc-800/80 pb-1 font-mono text-xs">
        <button
          type="button"
          onClick={() => setActiveTab("workbench")}
          className={`relative pb-2 font-semibold transition ${
            activeTab === "workbench"
              ? "text-emerald-400"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <span className="flex items-center gap-1.5">
            <span>🛡</span>
            <span>AUDIT WORKBENCH</span>
          </span>
          {activeTab === "workbench" && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-400"></span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("playground")}
          className={`relative pb-2 font-semibold transition ${
            activeTab === "playground"
              ? "text-emerald-400"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <span className="flex items-center gap-1.5">
            <span>⚡</span>
            <span>PLAYGROUND</span>
          </span>
          {activeTab === "playground" && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-400"></span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("sources")}
          className={`relative pb-2 font-semibold transition ${
            activeTab === "sources"
              ? "text-emerald-400"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <span className="flex items-center gap-1.5">
            <span>📄</span>
            <span>SOURCES ({sourceCount})</span>
          </span>
          {activeTab === "sources" && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-400"></span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("audits")}
          className={`relative pb-2 font-semibold transition ${
            activeTab === "audits"
              ? "text-emerald-400"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <span className="flex items-center gap-1.5">
            <span>⏱</span>
            <span>LOGS &amp; AUDITS</span>
          </span>
          {activeTab === "audits" && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-400"></span>
          )}
        </button>
      </nav>

      {/* Tab Panels */}
      <main>
        {activeTab === "workbench" && (
          <AuditWorkbench
            onVerified={handleVerificationComplete}
            activeSourceCount={sourceCount}
          />
        )}

        {activeTab === "playground" && (
          <VeritasPlayground onVerified={handleVerificationComplete} />
        )}

        {activeTab === "sources" && (
          <SourceManager
            onSourcesChanged={handleSourcesUpdated}
            refreshKey={sourceSyncKey}
          />
        )}

        {activeTab === "audits" && (
          <AuditLogsView refreshKey={auditSyncKey} />
        )}
      </main>
    </div>
  );
}
