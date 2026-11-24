"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Key, X, XCircle } from "lucide-react";

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

interface ApiKeyManagerProps {
  onClose?: () => void;
}

export default function ApiKeyManager({ onClose }: ApiKeyManagerProps) {
  const [keys, setKeys] = useState<AppKey[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [creating, setCreating] = useState<boolean>(false);
  const [appName, setAppName] = useState<string>("");
  const [rateLimit, setRateLimit] = useState<number>(60);
  const [createdKey, setCreatedKey] = useState<CreatedKeyResponse | null>(null);
  const [copiedKey, setCopiedKey] = useState<boolean>(false);
  const [copiedCurl, setCopiedCurl] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Compliance Webhook test state
  const [webhookUrl, setWebhookUrl] = useState<string>("");
  const [testingWebhook, setTestingWebhook] = useState<boolean>(false);
  const [webhookResult, setWebhookResult] = useState<{ success: boolean; message: string } | null>(null);

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

  const handleTestWebhook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!webhookUrl.trim()) return;
    setTestingWebhook(true);
    setWebhookResult(null);
    try {
      const res = await fetch("/api/compliance/webhook-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ webhook_url: webhookUrl.trim() }),
      });
      const data = await res.json();
      setWebhookResult(data);
    } catch (err) {
      setWebhookResult({
        success: false,
        message: err instanceof Error ? err.message : "Failed to connect to backend",
      });
    } finally {
      setTestingWebhook(false);
    }
  };

  const rawSecret = createdKey?.raw_key || createdKey?.api_key || "";
  const sampleApiKey = rawSecret || "vrt_live_YOUR_KEY_HERE";
  const apiOrigin = typeof window !== "undefined" ? window.location.origin : "http://localhost:8000";
  const sampleCurl = `curl -X POST ${apiOrigin}/v1/verify \\
  -H "Content-Type: application/json" \\
  -H "X-Veritas-Key: ${sampleApiKey}" \\
  -d '{
    "query": "What is the capital reserve allocation for FY 2026-27?",
    "policy": "strict"
  }'`;

  return (
    <div className="space-y-5">
      {/* Developer Header Banner with optional close button */}
      <div className="rounded-xl border border-[#27272A] bg-[#111114] p-5 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="flex h-6 w-6 items-center justify-center rounded bg-emerald-500/10 text-emerald-400 font-mono text-xs border border-emerald-500/20">
              <Key className="h-3.5 w-3.5" />
            </span>
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-200">
              Developer &amp; Application API Keys
            </span>
            <span className="rounded bg-[#18181B] border border-[#27272A] px-2 py-0.5 font-mono text-[10px] text-zinc-400">
              SHA-256 Hashed
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void fetchKeys()}
              className="rounded border border-[#27272A] bg-[#18181B] px-2.5 py-1 font-mono text-[11px] text-zinc-300 hover:text-zinc-100 hover:bg-[#222226] transition"
            >
              Refresh
            </button>
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="rounded border border-[#27272A] bg-[#18181B] p-1 text-zinc-400 hover:text-zinc-200 hover:bg-[#222226] transition"
                title="Close API Keys & Governance modal"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-zinc-400 leading-relaxed">
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
              className="rounded-lg border border-emerald-600/70 bg-emerald-950/60 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-emerald-300 hover:bg-emerald-900/60 transition"
            >
              {copiedKey ? "Copied!" : "Copy Key"}
            </button>
          </div>
        </div>
      )}

      {/* Create New Key Form */}
      <div className="rounded-xl border border-[#27272A] bg-[#111114] p-5 space-y-4">
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
              className="w-full rounded-md border border-[#27272A] bg-[#09090B] px-3 py-2 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono"
            />
          </div>

          <div className="space-y-1">
            <label className="block text-[10px] font-mono uppercase text-zinc-500">
              Rate Limit Tier
            </label>
            <select
              value={rateLimit}
              onChange={(e) => setRateLimit(Number(e.target.value))}
              className="w-full rounded-md border border-[#27272A] bg-[#09090B] px-3 py-2 text-xs text-zinc-200 focus:border-emerald-500/80 focus:outline-none font-mono"
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
              className="flex w-full items-center justify-center gap-2 rounded-md border border-emerald-600/70 bg-emerald-950/60 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-emerald-300 transition hover:bg-emerald-900/60 disabled:opacity-50"
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
      <div className="rounded-xl border border-[#27272A] bg-[#111114] p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-[#27272A] pb-3">
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
          <div className="divide-y divide-[#27272A]">
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
                    <span className="rounded bg-[#18181B] px-2 py-0.5 font-mono text-[10px] text-zinc-400 border border-[#27272A]">
                      {k.key_prefix}...
                    </span>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold border ${
                        k.is_active
                          ? "bg-emerald-950/80 text-emerald-400 border-emerald-800/60"
                          : "bg-rose-950/80 text-rose-400 border-rose-800/60"
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
      <div className="rounded-xl border border-[#27272A] bg-[#111114] p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300">
              Integration Quickstart (cURL)
            </span>
          </div>
          <button
            type="button"
            onClick={() => copyToClipboard(sampleCurl, true)}
            className="rounded border border-[#27272A] bg-[#18181B] px-2.5 py-1 font-mono text-[11px] text-zinc-300 hover:text-zinc-100 hover:bg-[#222226] transition"
          >
            {copiedCurl ? "Copied!" : "Copy Command"}
          </button>
        </div>

        <pre className="overflow-x-auto rounded-lg border border-[#27272A] bg-[#09090B] p-3.5 font-mono text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap break-all">
          <code>{sampleCurl}</code>
        </pre>
      </div>

      {/* Compliance Incident Alerting & Webhooks */}
      <div className="rounded-xl border border-[#27272A] bg-[#111114] p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-[#27272A] pb-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-zinc-300">
              Outbound Compliance Webhook Alerting
            </span>
            <span className="rounded bg-amber-950/70 border border-amber-800/60 px-2 py-0.5 font-mono text-[10px] text-amber-400">
              Real-time Invariant Dispatch
            </span>
          </div>
          <span className="font-mono text-[11px] text-zinc-500">
            Slack / Teams / SIEM Compatible
          </span>
        </div>

        <p className="text-xs text-zinc-400 leading-relaxed">
          When an audit results in <span className="text-rose-400 font-mono font-bold">ABSTAIN</span> (hallucination detected, numeric contradiction, or expired policy violation), MNB Veritas immediately dispatches a non-blocking asynchronous incident payload to notify risk teams.
        </p>

        <form onSubmit={handleTestWebhook} className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            type="url"
            required
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            placeholder="https://hooks.slack.com/services/... or https://your-domain.com/webhook"
            className="flex-1 rounded-lg border border-[#27272A] bg-[#09090B] px-3 py-2 font-mono text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-emerald-500/80 focus:outline-none"
          />
          <button
            type="submit"
            disabled={testingWebhook || !webhookUrl.trim()}
            className="rounded-lg border border-[#27272A] bg-[#18181B] px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-zinc-200 hover:bg-[#222226] transition disabled:opacity-50"
          >
            {testingWebhook ? "Sending..." : "Test Ping"}
          </button>
        </form>

        {webhookResult && (
          <div
            className={`rounded-lg p-3 font-mono text-xs border ${
              webhookResult.success
                ? "bg-emerald-950/40 border-emerald-800/60 text-emerald-300"
                : "bg-rose-950/40 border-rose-800/60 text-rose-300"
            }`}
          >
            {webhookResult.success ? (
              <CheckCircle2 className="h-3.5 w-3.5 inline mr-1 text-emerald-400" />
            ) : (
              <XCircle className="h-3.5 w-3.5 inline mr-1 text-rose-400" />
            )}
            {webhookResult.message}
          </div>
        )}
      </div>
    </div>
  );
}
