// Feedback states: alerts, empty, loading (skeleton), error, status dots and a progress bar.
// Every state is announced: role="alert" for problems, role="status" for loading and live updates.
import { AlertTriangle, CheckCircle2, Info, XCircle, type LucideIcon } from "lucide-react";
import { Button } from "./Button";

type Tone = "info" | "success" | "warning" | "danger";
const TONES: Record<Tone, { box: string; Icon: LucideIcon }> = {
  info: { box: "bg-info-bg text-info-fg", Icon: Info },
  success: { box: "bg-success-bg text-success-fg", Icon: CheckCircle2 },
  warning: { box: "bg-warning-bg text-warning-fg", Icon: AlertTriangle },
  danger: { box: "bg-danger-bg text-danger-fg", Icon: XCircle },
};

export function Alert({ tone = "info", title, children }: { tone?: Tone; title?: React.ReactNode; children?: React.ReactNode }) {
  const { box, Icon } = TONES[tone];
  return (
    <div role={tone === "danger" ? "alert" : "note"} className={`flex gap-3 rounded-lg px-4 py-3 text-sm ${box}`}>
      <Icon size={18} className="mt-0.5 flex-none" aria-hidden="true" />
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? "mt-0.5" : ""}>{children}</div>}
      </div>
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: React.ReactNode; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-border-strong px-6 py-10 text-center">
      <p className="text-base font-semibold text-fg">{title}</p>
      {children && <div className="max-w-prose text-sm text-muted">{children}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/** Grey placeholder bars while data loads. Hidden from screen readers; the wrapper announces "Loading". */
export function Skeleton({ lines = 3, label = "Loading…" }: { lines?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-2.5">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} aria-hidden="true" className={`h-3 animate-pulse rounded bg-surface-2 ${i % 3 === 1 ? "w-3/5" : "w-full"}`} />
      ))}
    </div>
  );
}

/** An API failure, with the server's own code and message, and a way to try again. */
export function ErrorState({ title, code, message, onRetry }: { title: string; code: string; message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-danger-fg/30 bg-danger-bg p-4 text-sm text-danger-fg">
      <p className="font-semibold">{title} ({code})</p>
      <p className="mt-1">{message}</p>
      {onRetry && <Button variant="danger" size="sm" className="mt-3" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function StatusDot({ tone, children }: { tone: "ok" | "off" | "warn" | "error"; children: React.ReactNode }) {
  const dot = { ok: "bg-ok-dot", off: "bg-off-dot", warn: "bg-warning-fg", error: "bg-danger-fg" }[tone];
  return (
    <span className="inline-flex items-center gap-2 text-[13px]">
      <span aria-hidden="true" className={`h-2 w-2 flex-none rounded-full ${dot}`} />
      {children}
    </span>
  );
}

/** Shows the SERVER's percentage; never computes one. */
export function ProgressBar({ percent, label }: { percent: number; label: string }) {
  const value = Math.max(0, Math.min(100, percent));
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}
         className="h-2 w-full overflow-hidden rounded-full bg-surface-2 shadow-[inset_0_0_0_1px_rgb(var(--border))]">
      <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${value}%` }} />
    </div>
  );
}
