// Small shared building blocks: badges, loading/error boxes, a card. Display only.
// R1: colours come from the design tokens (both themes). Labels, titles and MEANINGS are unchanged -
// these badges carry the benchmark honesty rules (real vs scripted, subset, registration, incomplete).
import type { ApiState } from "../api/useApi";
import { ErrorState } from "./feedback";

export { Card } from "./Card";

const tone = {
  green: "bg-success-bg text-success-fg",
  red: "bg-danger-bg text-danger-fg",
  amber: "bg-warning-bg text-warning-fg",
  slate: "bg-neutral-bg text-neutral-fg",
  blue: "bg-info-bg text-info-fg",
} as const;

export function Badge({ color, children, title }: { color: keyof typeof tone; children: React.ReactNode; title?: string }) {
  return <span title={title} className={`inline-block whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-semibold ${tone[color]}`}>{children}</span>;
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

/** Did the run cover its whole suite? Shown as the API reports it; "unknown" is never shown as full. */
export function ScopeBadge({ scope, registration }: { scope: string; registration: string }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      {scope === "subset" && <Badge color="amber" title="Only some of the suite's tasks: not a full-suite result">SUBSET</Badge>}
      {scope === "full" && <Badge color="slate">full suite</Badge>}
      {scope === "unknown" && <Badge color="slate" title="Task definitions were not stored">task set unknown</Badge>}
      {registration === "matches" && <Badge color="green" title="Matches its pre-registration">registered ✓</Badge>}
      {registration === "subset" && <Badge color="green" title="Each task matches its registered definition">registered ✓</Badge>}
      {registration === "differs" && <Badge color="red" title="Not the registered benchmark">DIFFERS from registration</Badge>}
    </span>
  );
}

export function CompleteBadge({ complete }: { complete: boolean }) {
  return complete ? <Badge color="green">complete</Badge> : <Badge color="amber">INCOMPLETE</Badge>;
}

/** Renders loading / error for any API state; calls `children` only when the data is ready. */
export function Loaded<T>({ state, children }: { state: ApiState<T> & { reload: () => void }; children: (data: T) => React.ReactNode }) {
  if (state.status === "loading") return <p role="status" className="text-muted">Loading…</p>;
  if (state.status === "error") {
    return <ErrorState title="Could not load" code={state.error.code} message={state.error.message} onRetry={state.reload} />;
  }
  return <>{children(state.data)}</>;
}
