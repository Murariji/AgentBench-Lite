// Cards and metric cards. A MetricCard shows ONE server value. `value={null}` means the value is NOT
// AVAILABLE (with the reason) - never shown as 0. A real zero is passed as 0 and shown as "0".

export function Card({ title, actions, children, className = "" }: {
  title?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-card border border-border bg-surface p-5 shadow-card ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          {title && <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h3>}
          {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function MetricCard({ label, value, suffix, detail, unavailableReason }: {
  label: string;
  value: React.ReactNode | null;     // null = not available (never rendered as 0)
  suffix?: React.ReactNode;
  detail?: React.ReactNode;
  unavailableReason?: string;
}) {
  const missing = value === null || value === undefined;
  return (
    <section aria-label={label} className="flex flex-col gap-1.5 rounded-card border border-border bg-surface px-5 py-4 shadow-card">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">{label}</h3>
      {missing ? (
        <>
          <p className="text-metric font-semibold text-muted" data-testid="metric-unavailable">Not available</p>
          {unavailableReason && <p className="text-[13px] text-muted">{unavailableReason}</p>}
        </>
      ) : (
        <>
          <p className="text-metric tabular-nums text-fg" data-testid="metric-value">
            {value}{suffix && <span className="ml-1 text-base font-medium text-muted">{suffix}</span>}
          </p>
          {detail && <div className="text-[13px] text-muted">{detail}</div>}
        </>
      )}
    </section>
  );
}
