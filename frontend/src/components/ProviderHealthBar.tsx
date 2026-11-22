"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CircuitState, LabProvider, ProviderHealth, ProvidersHealth } from "@/types/veritas";
import { btnGhost } from "./ui";

interface RawProviderStatus {
  lab: LabProvider;
  model?: string;
  state: CircuitState;
  failure_count?: number;
  consecutive_failures?: number;
  cooldown_seconds?: number;
}

interface RawProvidersResponse {
  backend?: string;
  redis_connected?: boolean;
  providers?: RawProviderStatus[] | Record<string, RawProviderStatus>;
}

const LABELS: Record<string, string> = {
  anthropic: "Claude",
  openai: "OpenAI",
  google: "Gemini",
  xai: "Grok",
};

function tone(p: ProviderHealth) {
  if (p.configured === false) return { pill: "border-zinc-800 bg-zinc-950/70 text-zinc-500", dot: "bg-zinc-600" };
  if (p.state === "CLOSED") return { pill: "border-emerald-700/60 bg-emerald-950/50 text-emerald-300", dot: "bg-emerald-400" };
  if (p.state === "HALF_OPEN") return { pill: "border-amber-700/60 bg-amber-950/50 text-amber-300", dot: "bg-amber-400" };
  return { pill: "border-rose-700/70 bg-rose-950/60 text-rose-300", dot: "bg-rose-400 animate-pulse" };
}

export function ProviderHealthBar({ refreshKey = 0, pollMs = 15000 }: { refreshKey?: number; pollMs?: number }) {
  const [data, setData] = useState<ProvidersHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resetting, setResetting] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api<RawProvidersResponse>("/v1/health/providers");
      const rawProviders = res?.providers;
      const provList: ProviderHealth[] = Array.isArray(rawProviders)
        ? rawProviders.map((item) => ({
            lab: item.lab,
            configured: true,
            model: item.model || item.lab,
            state: item.state,
            consecutive_failures: item.failure_count || item.consecutive_failures || 0,
            retry_after_s: item.cooldown_seconds || 0,
            backend: res.backend || (res.redis_connected ? "redis" : "memory"),
          }))
        : Object.values(rawProviders || {}).map((item) => ({
            lab: item.lab,
            configured: true,
            model: item.model || item.lab,
            state: item.state,
            consecutive_failures: item.failure_count || item.consecutive_failures || 0,
            retry_after_s: item.cooldown_seconds || 0,
            backend: res.backend || (res.redis_connected ? "redis" : "memory"),
          }));

      setData({
        backend: res.backend || (res.redis_connected ? "redis" : "memory"),
        providers: provList,
      });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gateway unreachable");
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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setResetting(null);
    }
  };

  const providers = data?.providers || [];

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/60 px-4 py-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Gateway</span>
        {!data && !error && <span className="font-mono text-zinc-500">checking…</span>}
        {error && !data && (
          <span className="rounded-full border border-rose-800/70 bg-rose-950/50 px-2.5 py-0.5 font-mono text-[11px] text-rose-300">
            offline — {error}
          </span>
        )}
        {providers.map((p) => {
          const t = tone(p);
          const canReset = p.state !== "CLOSED";
          return (
            <span
              key={p.lab}
              title={`${p.model ?? "active"} · failures ${p.consecutive_failures} · ${p.backend}`}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[11px] ${t.pill}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${t.dot}`} />
              <span className="font-semibold">{LABELS[p.lab] || p.lab}</span>
              <span className="opacity-80">
                {p.state === "OPEN" ? `OPEN ${Math.ceil(p.retry_after_s || 30)}s` : p.state}
              </span>
              {canReset && (
                <button
                  type="button"
                  disabled={resetting === p.lab}
                  onClick={() => void reset(p.lab)}
                  className="ml-0.5 rounded border border-current/30 px-1.5 text-[10px] font-semibold uppercase hover:bg-zinc-900 disabled:opacity-50"
                >
                  {resetting === p.lab ? "…" : "Reset"}
                </button>
              )}
            </span>
          );
        })}
      </div>
      <div className="flex items-center gap-2 font-mono text-[11px] text-zinc-400">
        {error && data && <span className="text-rose-300">{error}</span>}
        {data && <span className="rounded border border-zinc-800 bg-zinc-950 px-2 py-0.5 text-zinc-300">state: {data.backend}</span>}
        <button type="button" onClick={() => void load()} className={btnGhost}>
          Sync
        </button>
      </div>
    </div>
  );
}
