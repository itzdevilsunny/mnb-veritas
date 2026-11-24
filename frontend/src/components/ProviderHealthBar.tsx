"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import type { CircuitState, LabProvider, ProviderHealth, ProvidersHealth } from "@/types/veritas";

interface RawProviderStatus {
  lab: LabProvider;
  model?: string;
  state: CircuitState;
  configured?: boolean;
  reachable?: boolean;
  failure_count?: number;
  consecutive_failures?: number;
  cooldown_seconds?: number;
  cooldown_remaining?: number;
  last_error?: string;
  backend?: string;
}

interface RawProvidersResponse {
  backend?: string;
  redis_connected?: boolean;
  providers?: RawProviderStatus[] | Record<string, RawProviderStatus>;
  total_configured?: number;
  active_count?: number;
  open_count?: number;
  half_open_count?: number;
}

const LABELS: Record<string, string> = {
  anthropic: "Claude",
  openai: "OpenAI",
  google: "Gemini",
  xai: "Grok",
  ollama: "Ollama",
};

export function ProviderHealthBar({
  refreshKey = 0,
  pollMs = 10000,
  onResetComplete,
}: {
  refreshKey?: number;
  pollMs?: number;
  onResetComplete?: () => void;
}) {
  const [data, setData] = useState<ProvidersHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resetting, setResetting] = useState<string | null>(null);
  const [resettingAll, setResettingAll] = useState<boolean>(false);
  const [syncing, setSyncing] = useState<boolean>(false);

  const load = useCallback(async () => {
    try {
      setSyncing(true);
      const res = await api<RawProvidersResponse>("/v1/health/providers");
      const rawProviders = res?.providers;

      const normalizeItem = (item: RawProviderStatus, key?: string): ProviderHealth => {
        const labKey = (item.lab || key || "ollama") as LabProvider;
        const isConfigured = item.configured === true;
        return {
          lab: labKey,
          configured: isConfigured,
          model: item.model || "",
          state: item.state || "CLOSED",
          consecutive_failures: item.failure_count ?? item.consecutive_failures ?? 0,
          retry_after_s: item.cooldown_remaining ?? item.cooldown_seconds ?? 0,
          backend: res.backend || (res.redis_connected ? "redis" : "memory"),
          reachable: item.reachable,
        };
      };

      let provList: ProviderHealth[] = [];
      if (Array.isArray(rawProviders)) {
        provList = rawProviders.map((item) => normalizeItem(item));
      } else if (rawProviders && typeof rawProviders === "object") {
        provList = Object.entries(rawProviders).map(([k, item]) => normalizeItem(item, k));
      }

      setData({
        backend: res.backend || (res.redis_connected ? "redis" : "memory"),
        providers: provList,
      });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gateway unreachable");
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  useEffect(() => {
    if (pollMs <= 0) return;
    const id = window.setInterval(() => void load(), pollMs);
    return () => window.clearInterval(id);
  }, [load, pollMs]);

  const reset = async (lab: string) => {
    setResetting(lab);
    try {
      await api(`/v1/health/providers/${lab}/reset`, { method: "POST" });
      await load();
      if (onResetComplete) onResetComplete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setResetting(null);
    }
  };

  const resetAll = async () => {
    setResettingAll(true);
    try {
      await fetch("/api/health/providers/reset-all", { method: "POST" });
      await load();
      if (onResetComplete) onResetComplete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset all failed");
    } finally {
      setResettingAll(false);
    }
  };

  const providers = data?.providers || [];
  const openCount = providers.filter((p) => p.state === "OPEN").length;
  const halfOpenCount = providers.filter((p) => p.state === "HALF_OPEN").length;
  const isRedis = data?.backend === "redis";

  return (
    <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-lg border border-[#27272A] bg-[#111114] px-3 py-2 text-xs font-mono">
      {/* Left: Providers Status Dots */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
          GATEWAY
        </span>

        {providers.map((p) => {
          const isConfigured = p.configured === true;
          const isUnreachable = p.state === "UNREACHABLE" || p.reachable === false;
          const isOpen = p.state === "OPEN";
          const isHalfOpen = p.state === "HALF_OPEN";
          const isClosed = p.state === "CLOSED" && isConfigured && !isUnreachable;

          let dotClass = "bg-zinc-600";
          let statusText = "UNCONFIGURED";
          let badgeBorder = "border-[#27272A] bg-[#141416] text-zinc-500";

          if (!isConfigured) {
            dotClass = "bg-zinc-600";
            statusText = "UNCONFIGURED";
            badgeBorder = "border-[#27272A] bg-[#141416] text-zinc-500";
          } else if (isUnreachable) {
            dotClass = "bg-amber-500/80";
            statusText = "OFFLINE";
            badgeBorder = "border-amber-900/40 bg-amber-950/20 text-amber-400";
          } else if (isOpen) {
            dotClass = "bg-rose-500 animate-pulse";
            statusText = `OPEN · Tripped${p.retry_after_s > 0 ? ` (${Math.ceil(p.retry_after_s)}s)` : ""}`;
            badgeBorder = "border-rose-900/60 bg-rose-950/40 text-rose-300";
          } else if (isHalfOpen) {
            dotClass = "bg-amber-400 animate-pulse";
            statusText = "PROBING";
            badgeBorder = "border-amber-900/60 bg-amber-950/40 text-amber-300";
          } else if (isClosed) {
            dotClass = "bg-emerald-400";
            statusText = "ACTIVE";
            badgeBorder = "border-emerald-900/40 bg-emerald-950/30 text-emerald-300";
          }

          return (
            <div
              key={p.lab}
              title={`${LABELS[p.lab] || p.lab} · ${statusText} · Model: ${p.model || "(none)"} · Failures: ${p.consecutive_failures}`}
              className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] ${badgeBorder}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${dotClass}`} />
              <span className="font-semibold text-zinc-200">{LABELS[p.lab] || p.lab}</span>
              <span className="text-[10px] opacity-75">{statusText}</span>
              {(isOpen || isHalfOpen) && (
                <button
                  type="button"
                  disabled={resetting === p.lab}
                  onClick={() => void reset(p.lab)}
                  title={`Reset ${LABELS[p.lab] || p.lab} circuit breaker`}
                  className="ml-1.5 inline-flex items-center gap-1 rounded border border-rose-600/70 bg-rose-900/80 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-rose-100 hover:bg-rose-800 transition disabled:opacity-50"
                >
                  <RotateCcw className={`h-2.5 w-2.5 ${resetting === p.lab ? "animate-spin" : ""}`} />
                  <span>{resetting === p.lab ? "…" : "reset"}</span>
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Right: Summary Badge & State Cache Indicator */}
      <div className="flex items-center gap-2 text-[11px]">
        {error && <span className="text-rose-400 text-[10px]">{error}</span>}

        {/* Global Reset All Button when any circuit is tripped */}
        {(openCount > 0 || halfOpenCount > 0) && (
          <button
            type="button"
            disabled={resettingAll}
            onClick={() => void resetAll()}
            title="Reset all tripped circuit breakers to CLOSED"
            className="inline-flex items-center gap-1 rounded border border-rose-700/60 bg-rose-950/80 px-2 py-0.5 text-[10px] font-semibold text-rose-200 hover:bg-rose-900/80 transition disabled:opacity-50"
          >
            <RotateCcw className={`h-2.5 w-2.5 ${resettingAll ? "animate-spin" : ""}`} />
            <span>{resettingAll ? "RESETTING..." : "RESET ALL CIRCUITS"}</span>
          </button>
        )}

        {/* Circuit summary badge */}
        <span
          className={`rounded border px-2 py-0.5 font-semibold text-[10px] ${
            openCount > 0
              ? "border-rose-800/80 bg-rose-950/50 text-rose-300"
              : halfOpenCount > 0
              ? "border-amber-800/80 bg-amber-950/50 text-amber-300"
              : "border-emerald-800/60 bg-emerald-950/30 text-emerald-400"
          }`}
        >
          {openCount > 0
            ? `CIRCUITS ${openCount} OPEN`
            : halfOpenCount > 0
            ? `CIRCUITS ${halfOpenCount} PROBING`
            : "ALL CIRCUITS CLOSED"}
        </span>

        {/* Distributed cache backend */}
        <span className="rounded border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-[10px] text-zinc-400">
          CACHE: <span className="text-zinc-200">{isRedis ? "REDIS" : "MEMORY"}</span>
        </span>

        <button
          type="button"
          onClick={() => void load()}
          disabled={syncing}
          title="Sync live gateway health"
          className="inline-flex h-6 w-6 items-center justify-center rounded border border-[#27272A] bg-[#18181B] text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition"
        >
          <RefreshCw className={`h-3 w-3 ${syncing ? "animate-spin text-zinc-200" : ""}`} />
        </button>
      </div>
    </div>
  );
}
