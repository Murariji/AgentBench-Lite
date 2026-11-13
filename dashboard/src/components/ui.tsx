// Small shared building blocks: badges, loading/error boxes, a card. Display only.
import type { ApiState } from "../api/useApi";

const tone = {
  green: "bg-emerald-100 text-emerald-800",
  red: "bg-red-100 text-red-800",
  amber: "bg-amber-100 text-amber-900",
  slate: "bg-slate-100 text-slate-700",
  blue: "bg-sky-100 text-sky-800",
} as const;

export function Badge({ color, children, title }: { color: keyof typeof tone; children: React.ReactNode; title?: string }) {
  return <span title={title} className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${tone[color]}`}>{children}</span>;
}

/** REAL model or SCRIPTED test agent - shown on every run, everywhere. */
export function KindBadge({ kind }: { kind: string }) {
  return kind === "real"
    ? <Badge color="blue">REAL LLM</Badge>
    : <Badge color="slate" title="Fixed answers written in advance - not AI">SCRIPTED</Badge>;
}

export function OutcomeBadge({ outcome }: { outcome: string }) {
  if (outcome === "passed") return <Badge color="green">passed</Badge>;
  if (outcome === "failed") return <Badge color="red">failed</Badge>;
  if (outcome === "infra_error") return <Badge color="amber" title="Not an agent failure">infra error</Badge>;
  return <Badge color="slate">{outcome}</Badge>;
}

export function CompleteBadge({ complete }: { complete: boolean }) {
  return complete ? <Badge color="green">complete</Badge> : <Badge color="amber">INCOMPLETE</Badge>;
}

export function Card({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      {title && <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h3>}
      {children}
    </section>
  );
}

/** Renders loading / error for any API state; calls `children` only when the data is ready. */
export function Loaded<T>({ state, children }: { state: ApiState<T> & { reload: () => void }; children: (data: T) => React.ReactNode }) {
  if (state.status === "loading") return <p role="status" className="text-slate-500">Loading…</p>;
  if (state.status === "error") {
    return (
      <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
        <p className="font-semibold">Could not load ({state.error.code})</p>
        <p className="mt-1">{state.error.message}</p>
        <button onClick={state.reload} className="mt-3 rounded bg-red-700 px-3 py-1 text-white hover:bg-red-800">
          Try again
        </button>
      </div>
    );
  }
  return <>{children(state.data)}</>;
}
