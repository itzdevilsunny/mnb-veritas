"use client";

import React, { useCallback, useState } from "react";
import {
  Activity,
  Database,
  FileText,
  Key,
  ShieldCheck,
  X,
} from "lucide-react";
import AuditWorkbench from "@/components/AuditWorkbench";
import SourceManager from "@/components/SourceManager";
import AuditLogsView from "@/components/AuditLogsView";
import BenchmarkRunner from "@/components/BenchmarkRunner";
import ApiKeyManager from "@/components/ApiKeyManager";
import type { ManagedSource } from "@/types/veritas";

type TabId = "workbench" | "benchmark" | "sources" | "audits";

export default function VeritasApp() {
  const [activeTab, setActiveTab] = useState<TabId>("workbench");
  const [showKeysModal, setShowKeysModal] = useState<boolean>(false);
  const [sourceCount, setSourceCount] = useState<number>(4);
  const [auditSyncKey, setAuditSyncKey] = useState<number>(0);
  const [sourceSyncKey, setSourceSyncKey] = useState<number>(0);

  const handleVerificationComplete = useCallback(() => {
    setAuditSyncKey((prev) => prev + 1);
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
            </div>
            <div className="font-mono text-[10px] tracking-wide text-zinc-500 uppercase">
              Forensic Regulatory &amp; Gazette Verification Terminal
            </div>
          </div>
        </div>

        {/* Secondary Governance & Scoped API Key Drawer Trigger */}
        <div className="flex items-center">
          <button
            type="button"
            onClick={() => setShowKeysModal(true)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-[#27272A] bg-[#111114] text-zinc-400 hover:text-zinc-200 hover:bg-[#18181B] transition font-mono text-[11px] whitespace-nowrap shadow-sm"
            title="Provision per-app API keys, test webhooks & view SDK quickstart"
          >
            <Key className="h-3.5 w-3.5 text-emerald-400" />
            <span>API Keys &amp; Governance</span>
          </button>
        </div>
      </header>

      {/* Workstation Navigation Bar: 4 Core Verification Views */}
      <nav className="flex items-center border-b border-[#27272A] pb-2 font-mono text-xs overflow-x-auto gap-1">
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
      </main>

      {/* API Keys & Governance Secondary Modal */}
      {showKeysModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto"
          onClick={() => setShowKeysModal(false)}
        >
          <div
            className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-xl border border-[#27272A] bg-[#09090B] p-6 shadow-2xl space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <ApiKeyManager onClose={() => setShowKeysModal(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
