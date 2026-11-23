"use client";

import React, { useCallback, useEffect, useState } from "react";

interface AppKey {
  id?: string;
  key_prefix: string;
  app_name: string;
  rate_limit_per_minute: number;
  created_at: string;
  is_active: boolean;
}

interface CreatedKeyResponse {
  id?: string;
  key_prefix: string;
  raw_key?: string;
  api_key?: string;
  app_name: string;
  rate_limit_per_minute: number;
  created_at: string;
}

export default function ApiKeyManager() {
  const [keys, setKeys] = useState<AppKey[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [creating, setCreating] = useState<boolean>(false);
  const [appName, setAppName] = useState<string>("");
  const [rateLimit, setRateLimit] = useState<number>(60);
  const [createdKey, setCreatedKey] = useState<CreatedKeyResponse | null>(null);
  const [copiedKey, setCopiedKey] = useState<boolean>(false);
  const [copiedCurl, setCopiedCurl] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchKeys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/keys", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setKeys(Array.isArray(data) ? data : []);
      } else {
        const err = await res.json();
        setError(err.detail || "Failed to load API keys");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchKeys();
  }, [fetchKeys]);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!appName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          app_name: appName.trim(),
          rate_limit_per_minute: Number(rateLimit),
        }),
      });
      if (res.ok) {
        const data: CreatedKeyResponse = await res.json();
        setCreatedKey(data);
        setAppName("");
        await fetchKeys();
      } else {
        const err = await res.json();
        setError(err.detail || "Failed to create API key");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create API key");
    } finally {
      setCreating(false);
    }
  };

  const handleRevokeKey = async (prefix: string) => {
    if (!window.confirm(`Revoke API key prefix ${prefix}? External apps using this key will immediately receive 401 Unauthorized.`)) {
      return;
    }
    try {
      const res = await fetch(`/api/auth/keys/${encodeURIComponent(prefix)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        await fetchKeys();
      } else {
        const err = await res.json();
        setError(err.detail || "Failed to revoke key");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to revoke key");
    }
  };

  const copyToClipboard = (text: string, isCurl = false) => {
    void navigator.clipboard.writeText(text);
    if (isCurl) {
      setCopiedCurl(true);
      setTimeout(() => setCopiedCurl(false), 2000);
    } else {
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    }
  };

  const rawSecret = createdKey?.raw_key || createdKey?.api_key || "";
  const sampleApiKey = rawSecret || "vrt_live_YOUR_KEY_HERE";
  const sampleCurl = `curl -X POST https://mnb-veritas.onrender.com/api/veritas/v1/verify \\
  -H "Content-Type: application/json" \\
  -H "X-Veritas-Key: ${sampleApiKey}" \\
  -d '{
    "query": "What is the capital reserve allocation for FY 2026-27?",
    "policy": "strict"
  }'`;

  return (
    <div className="space-y-6">
      {/* Developer Header Banner */}
      <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-emerald-500/20 text-emerald-400 font-mono text-xs">
              🔑
            </span>
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-200">
              Developer &amp; Application API Keys
            </span>
            <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
              SHA-256 Hashed
            </span>
          </div>
          <button
            type="button"
            onClick={() => void fetchKeys()}
            className="font-mono text-[11px] text-emerald-400 hover:text-emerald-300 transition"
          >
            Refresh Keys
          </button>
        </div>
        <p className="text-xs text-zinc-400">
          Provision secure application keys for downstream microservices, compliance automations, or internal agent workflows. Each key enforces token-bucket rate limits and multi-model verification governance.
        </p>
      </div>

      {/* Newly Created Key Alert (Secret Display) */}
      {createdKey && (
        <div className="rounded-xl border border-emerald-500/60 bg-emerald-950/40 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="font-mono text-xs font-bold text-emerald-300">
                API Key Generated Successfully
              </span>
            </div>
            <span className="font-mono text-[10px] uppercase text-emerald-400/80">
              Copy Now (Hidden Forever After)
            </span>
          </div>

          <p className="text-xs text-zinc-300">
            For security, this raw secret key is displayed only once and stored strictly as a SHA-256 hash.
          </p>

          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={rawSecret}
              className="flex-1 rounded-lg border border-emerald-500/50 bg-[#080C0E] px-3 py-2 font-mono text-xs text-emerald-200 selection:bg-emerald-500/30 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => copyToClipboard(rawSecret)}
              className="rounded-lg bg-emerald-500 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-zinc-950 hover:bg-emerald-400 transition"
            >
              {copiedKey ? "Copied!" : "Copy Key"}
            </button>
          </div>
        </div>
      )}

      {/* Create New Key Form */}
      <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-4">
        <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300">
          Generate New Application Key
        </h3>

        <form onSubmit={handleCreateKey} className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              Application Name / Identifier
            </label>
            <input
              type="text"
              required
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              placeholder="e.g. RiskEngine-Prod or SlackBot"
              className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-3 py-2 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono"
            />
          </div>

          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              Rate Limit Tier
            </label>
            <select
              value={rateLimit}
              onChange={(e) => setRateLimit(Number(e.target.value))}
              className="w-full rounded-md border border-zinc-800 bg-[#0B0F12] px-3 py-2 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono"
            >
              <option value={30}>30 requests / minute (Standard)</option>
              <option value={60}>60 requests / minute (Production)</option>
              <option value={120}>120 requests / minute (Enterprise)</option>
              <option value={300}>300 requests / minute (High-Throughput Batch)</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={creating || !appName.trim()}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-emerald-500 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-zinc-950 transition hover:bg-emerald-400 disabled:opacity-50"
            >
              {creating ? "Generating..." : "Generate Key"}
            </button>
          </div>
        </form>

        {error && (
          <div className="rounded-lg border border-rose-800/80 bg-rose-950/40 p-3 font-mono text-xs text-rose-300">
            {error}
          </div>
        )}
      </div>

      {/* Active Keys Table */}
      <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
          <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300">
            Active Registered Keys ({keys.length})
          </span>
          <span className="font-mono text-[11px] text-zinc-500">
            Enforced at Gateway Layer
          </span>
        </div>

        {loading ? (
          <div className="py-8 text-center font-mono text-xs text-zinc-500">
            Loading active keys...
          </div>
        ) : keys.length === 0 ? (
          <div className="py-8 text-center font-mono text-xs text-zinc-500">
            No application keys registered yet. Generate one above to integrate external apps.
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/60">
            {keys.map((k) => (
              <div
                key={k.key_prefix}
                className="flex flex-wrap items-center justify-between gap-3 py-3"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-xs text-zinc-200">
                      {k.app_name}
                    </span>
                    <span className="rounded bg-zinc-800/80 px-2 py-0.5 font-mono text-[10px] text-zinc-400 border border-zinc-700/60">
                      {k.key_prefix}...
                    </span>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold ${
                        k.is_active
                          ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60"
                          : "bg-rose-950/80 text-rose-400 border border-rose-800/60"
                      }`}
                    >
                      {k.is_active ? "ACTIVE" : "REVOKED"}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 font-mono text-[11px] text-zinc-500">
                    <span>Limit: {k.rate_limit_per_minute} req/min</span>
                    <span>Created: {new Date(k.created_at).toISOString().slice(0, 10)}</span>
                  </div>
                </div>

                {k.is_active && (
                  <button
                    type="button"
                    onClick={() => void handleRevokeKey(k.key_prefix)}
                    className="rounded border border-rose-900/60 bg-rose-950/30 px-2.5 py-1 font-mono text-[11px] text-rose-400 hover:bg-rose-900/40 transition"
                  >
                    Revoke Key
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Integration Code Snippet */}
      <div className="rounded-xl border border-zinc-800 bg-[#0E1318]/90 p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300">
              Integration Quickstart (cURL)
            </span>
          </div>
          <button
            type="button"
            onClick={() => copyToClipboard(sampleCurl, true)}
            className="font-mono text-[11px] text-emerald-400 hover:text-emerald-300 transition"
          >
            {copiedCurl ? "Copied!" : "Copy Command"}
          </button>
        </div>

        <pre className="overflow-x-auto rounded-lg border border-zinc-800/80 bg-[#080C0E] p-3.5 font-mono text-xs text-zinc-300 leading-relaxed">
          <code>{sampleCurl}</code>
        </pre>
      </div>
    </div>
  );
}
