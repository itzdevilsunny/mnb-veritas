"use client";

import React, { useCallback, useState } from "react";
import {
  Activity,
  Database,
  FileText,
  Key,
  ShieldCheck,
} from "lucide-react";
import AuditWorkbench from "@/components/AuditWorkbench";
import SourceManager from "@/components/SourceManager";
import AuditLogsView from "@/components/AuditLogsView";
import BenchmarkRunner from "@/components/BenchmarkRunner";
import ApiKeyManager from "@/components/ApiKeyManager";
import { ProviderHealthBar } from "@/components/ProviderHealthBar";
import type { ManagedSource } from "@/types/veritas";

type TabId = "workbench" | "benchmark" | "sources" | "audits" | "keys";

export default function VeritasApp() {
  const [activeTab, setActiveTab] = useState<TabId>("workbench");
  const [sourceCount, setSourceCount] = useState<number>(4);
  const [auditSyncKey, setAuditSyncKey] = useState<number>(0);
  const [sourceSyncKey, setSourceSyncKey] = useState<number>(0);
  const [gatewaySyncKey, setGatewaySyncKey] = useState<number>(0);

  const handleVerificationComplete = useCallback(() => {
    setAuditSyncKey((prev) => prev + 1);
    setGatewaySyncKey((prev) => prev + 1);
  }, []);

  const handleSourcesUpdated = useCallback((sources: ManagedSource[]) => {
    setSourceCount(sources.length);
    setSourceSyncKey((prev) => prev + 1);
  }, []);

  const tabs = [
    { id: "workbench" as TabId, label: "Audit Workbench", icon: ShieldCheck },
    { id: "benchmark" as TabId, label: "Benchmark Lab", icon: Activity },
    { id: "sources" as TabId, label: `Sources (${sourceCount})`, icon: Database },
    { id: "audits" as TabId, label: "Logs & Audits", icon: FileText },
    { id: "keys" as TabId, label: "API Keys & Governance", icon: Key },
  ];

  return (
    <div
      suppressHydrationWarning
      className="mx-auto min-h-screen max-w-7xl px-4 py-5 space-y-4 font-sans text-zinc-100"
    >
      {/* Institutional Forensic Workstation Top Header */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#27272A] pb-3.5">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-[#18181B] border border-[#27272A] text-emerald-400 font-mono font-bold text-xs shadow-sm">
            V
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold tracking-tight text-zinc-100">
                MNB VERITAS
              </span>
              <span className="rounded border border-[#27272A] bg-[#18181B] px-1.5 py-0.2 font-mono text-[10px] text-zinc-400">
                v1.4
              </span>
              <span className="inline-flex items-center gap-1.5 rounded border border-emerald-900/50 bg-emerald-950/30 px-2 py-0.5 text-emerald-400 font-mono text-[10px] font-medium">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                ACTIVE AUDIT
              </span>
            </div>
            <div className="font-mono text-[10px] tracking-wide text-zinc-500 uppercase">
              Forensic Regulatory &amp; Gazette Verification Terminal
            </div>
          </div>
        </div>

        {/* Global Workstation Meta */}
        <div className="flex items-center gap-2 font-mono text-[11px] text-zinc-400">
          <span className="rounded border border-[#27272A] bg-[#111114] px-2.5 py-1 text-zinc-400">
            SECURITY PROFILE: <span className="font-semibold text-zinc-200">ENTERPRISE ZERO-PII</span>
          </span>
        </div>
      </header>

      {/* Single Live Provider Circuit Bar */}
      <ProviderHealthBar
        refreshKey={gatewaySyncKey}
        pollMs={12000}
        onResetComplete={() => setAuditSyncKey((k) => k + 1)}
      />

      {/* Workstation Navigation Tabs */}
      <nav className="flex items-center gap-1 border-b border-[#27272A] pb-2 font-mono text-xs overflow-x-auto">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md transition-all font-medium whitespace-nowrap ${
                isActive
                  ? "bg-[#18181B] text-zinc-100 border border-[#27272A] shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-[#141416]"
              }`}
            >
              <Icon className={`h-3.5 w-3.5 ${isActive ? "text-emerald-400" : "text-zinc-500"}`} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Active Workstation Workspace View */}
      <main className="pt-1">
        {activeTab === "workbench" && (
          <AuditWorkbench
            onVerified={handleVerificationComplete}
            activeSourceCount={sourceCount}
          />
        )}
        {activeTab === "benchmark" && <BenchmarkRunner />}
        {activeTab === "sources" && (
          <SourceManager
            onSourcesChanged={handleSourcesUpdated}
            refreshKey={sourceSyncKey}
          />
        )}
        {activeTab === "audits" && <AuditLogsView refreshKey={auditSyncKey} />}
        {activeTab === "keys" && <ApiKeyManager />}
      </main>
    </div>
  );
}
