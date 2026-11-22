import type { ReactNode } from "react";
import type { Verdict } from "@/types/veritas";

export const NO_ANSWER = "No answer possible";

export const VERDICT_STYLE: Record<Verdict, string> = {
  APPROVE: "border-emerald-700/70 bg-emerald-950/70 text-emerald-300",
  QUALIFY: "border-amber-700/70 bg-amber-950/70 text-amber-300",
  ABSTAIN: "border-rose-700/70 bg-rose-950/70 text-rose-300",
  ESCALATE: "border-violet-700/70 bg-violet-950/70 text-violet-300",
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`rounded-full border px-3 py-1 font-mono text-xs font-bold ${VERDICT_STYLE[verdict]}`}>
      {verdict}
    </span>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-zinc-800 bg-zinc-900/50 p-5 ${className}`}>{children}</section>;
}

export function Label({ children }: { children: ReactNode }) {
  return <label className="block text-xs font-medium uppercase tracking-wider text-zinc-400">{children}</label>;
}

export function Chip({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <span
      className={`rounded px-2 py-0.5 font-mono text-[11px] ${
        ok ? "bg-emerald-950/60 text-emerald-300" : "bg-rose-950/60 text-rose-300"
      }`}
    >
      {children}
    </span>
  );
}

export const inputCls =
  "w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-sky-500 focus:outline-none";

export const btnPrimary =
  "rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-50";

export const btnGhost =
  "rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-50";

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="rounded-lg border border-rose-800 bg-rose-950/60 px-3 py-2 text-xs text-rose-200">
      {message}
    </div>
  );
}
