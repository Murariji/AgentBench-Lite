// DEVELOPMENT ONLY (/design): every base component in the current theme, or both themes side by side.
// App.tsx registers this route only when import.meta.env.DEV is true, so the production build does not
// contain it (scripts/check-dev-only.mjs fails the build if it ever does).
// The sample rows are copied from stored runs; nothing here calls the API.
import { useState } from "react";
import { Button } from "../components/Button";
import { Card, MetricCard } from "../components/Card";
import { Alert, EmptyState, ErrorState, ProgressBar, Skeleton, StatusDot } from "../components/feedback";
import { Checkbox, Field, Input, Select } from "../components/form";
import { DataTable } from "../components/Table";
import { Badge, CompleteBadge, KindBadge, OutcomeBadge, ScopeBadge } from "../components/ui";
import { ThemeSwitcher } from "../theme/ThemeSwitcher";
import { useTheme } from "../theme/ThemeProvider";

export const DESIGN_PAGE_MARKER = "Design system (development only)";

const TOKENS = ["bg", "surface", "surface-2", "border", "border-strong", "fg", "muted", "accent", "accent-soft",
                "success-fg", "warning-fg", "danger-fg", "info-fg", "neutral-fg"];

type SampleRun = { id: string; suite: string; kind: string; scope: string; reg: string; text: string; calls: number };
const SAMPLE_RUNS: SampleRun[] = [
  { id: "b36e1e4a", suite: "shop-hard", kind: "real", scope: "full", reg: "matches", text: "9/9 (100.0%)", calls: 63 },
  { id: "f8e7c26f", suite: "shop-hard", kind: "real", scope: "subset", reg: "subset", text: "2/2 (100.0%)", calls: 14 },
  { id: "8d9b2ea1", suite: "shop-hard", kind: "scripted", scope: "full", reg: "matches", text: "3/9 (33.3%)", calls: 18 },
  { id: "743cde41", suite: "shop", kind: "real", scope: "full", reg: "unregistered", text: "10/10 (100.0%)", calls: 57 },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-base font-semibold text-fg">{title}</h2>
      {children}
    </section>
  );
}

function Gallery() {
  const [budget, setBudget] = useState("100");
  return (
    <div className="flex flex-col gap-8 bg-bg p-6 text-body text-fg sm:p-8">
      <Section title="Colour tokens">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {TOKENS.map((t) => (
            <div key={t} className="flex flex-col gap-1">
              <div className="h-10 rounded-lg shadow-[inset_0_0_0_1px_rgb(var(--border-strong))]" style={{ background: `rgb(var(--${t}))` }} />
              <span className="font-mono text-xs text-muted">--{t}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Typography">
        <Card>
          <div className="flex flex-col gap-2">
            <p className="text-title">Page title 26</p>
            <p className="text-base font-semibold">Section title 16</p>
            <p className="text-body">Body text 15: readable at a glance on a wide screen.</p>
            <p className="text-table">Table text 14 · <span className="font-mono text-[13px] text-muted">b36e1e4a</span></p>
            <p className="text-metric tabular-nums">9/9 <span className="text-base font-medium text-muted">(100.0%)</span></p>
          </div>
        </Card>
      </Section>

      <Section title="Metric cards (unavailable is never 0)">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Stored runs" value={8} detail="6 real-LLM runs · server counts" />
          <MetricCard label="Infra errors" value={0} detail="a real zero, reported by the server" />
          <MetricCard label="Latest real full-suite run" value="9/9" suffix="(100.0%)" detail={<KindBadge kind="real" />} />
          <MetricCard label="Active run" value={null} unavailableReason="The API could not be reached." />
        </div>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap gap-3">
          <Button variant="primary">Estimate</Button>
          <Button>Compare</Button>
          <Button variant="ghost">Cancel</Button>
          <Button variant="danger">Stop run</Button>
          <Button variant="primary" disabled>Start REAL run</Button>
          <Button size="sm">Small</Button>
        </div>
      </Section>

      <Section title="Form controls">
        <Card>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Suite" hint="the server validates every request">
              <Select defaultValue="shop-hard"><option>shop-hard</option><option>shop</option></Select>
            </Field>
            <Field label="Budget (hard cap on Gemini requests)" error={budget.trim() ? undefined : "a real run needs a budget"}>
              <Input type="number" min={1} value={budget} onChange={(e) => setBudget(e.target.value)} />
            </Field>
            <div className="flex items-end pb-2"><Checkbox label="I confirm: send real requests to Gemini" /></div>
          </div>
        </Card>
      </Section>

      <Section title="Honesty badges (labels and meanings unchanged)">
        <div className="flex flex-wrap items-center gap-2">
          <KindBadge kind="real" /> <KindBadge kind="scripted" />
          <ScopeBadge scope="subset" registration="subset" /> <ScopeBadge scope="full" registration="matches" />
          <ScopeBadge scope="unknown" registration="unknown" /> <ScopeBadge scope="full" registration="differs" />
          <CompleteBadge complete /> <CompleteBadge complete={false} />
          <OutcomeBadge outcome="passed" /> <OutcomeBadge outcome="failed" /> <OutcomeBadge outcome="infra_error" />
          <Badge color="slate">tools not recorded</Badge>
        </div>
      </Section>

      <Section title="Status and progress">
        <div className="flex flex-wrap gap-6">
          <StatusDot tone="ok">API connected</StatusDot>
          <StatusDot tone="off">Real runs disabled</StatusDot>
          <StatusDot tone="warn">Incomplete</StatusDot>
          <StatusDot tone="error">API unreachable</StatusDot>
        </div>
        <ProgressBar percent={22} label="sample progress" />
      </Section>

      <Section title="Alerts">
        <Alert tone="info" title="Tools not recorded">Shown as unknown, never assumed equal to a known version.</Alert>
        <Alert tone="success">The server would accept this run.</Alert>
        <Alert tone="warning" title="Subset">A subset is not a full-suite score: a separate marker, never on a trend line.</Alert>
        <Alert tone="danger" title="The server would NOT start this run">real Gemini runs are disabled on this server</Alert>
      </Section>

      <Section title="Empty, loading and error states">
        <div className="grid gap-4 lg:grid-cols-3">
          <EmptyState title="No comparable full-suite runs yet">Only registered, full-suite, complete runs are joined by a line.</EmptyState>
          <Card><Skeleton lines={4} /></Card>
          <ErrorState title="Could not load" code="network_error" message="Cannot reach the API at http://127.0.0.1:8000. Is it running?" onRetry={() => undefined} />
        </div>
      </Section>

      <Section title="Table">
        <Card className="p-0 overflow-hidden">
          <DataTable<SampleRun>
            label="sample runs"
            rows={SAMPLE_RUNS}
            rowKey={(r) => r.id}
            columns={[
              { key: "id", header: "Run", cell: (r) => <span className="font-mono text-[13px] font-semibold text-accent">{r.id}</span> },
              { key: "suite", header: "Suite", cell: (r) => r.suite },
              { key: "kind", header: "Agent", cell: (r) => <KindBadge kind={r.kind} /> },
              { key: "scope", header: "Scope", cell: (r) => (
                <span className="inline-flex gap-1">
                  <ScopeBadge scope={r.scope} registration={r.reg} />
                  {r.reg === "unregistered" && <Badge color="slate">unregistered</Badge>}
                </span>) },
              { key: "rate", header: "Pass rate", cell: (r) => r.text },
              { key: "calls", header: "LLM calls", cell: (r) => r.calls, align: "right" },
            ]}
          />
        </Card>
      </Section>
    </div>
  );
}

export function DesignPage() {
  const { resolved } = useTheme();
  const [both, setBoth] = useState(false);
  return (
    <div className="min-h-screen bg-bg text-fg">
      <header className="flex flex-wrap items-center gap-4 border-b border-border px-6 py-3 sm:px-8">
        <div>
          <h1 className="text-title">{DESIGN_PAGE_MARKER}</h1>
          <p className="text-sm text-muted">Every base component, from the design tokens. Current theme: {resolved}.</p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-4">
          <Checkbox label="Show both themes side by side" checked={both} onChange={(e) => setBoth(e.target.checked)} />
          <ThemeSwitcher />
        </div>
      </header>
      {both ? (
        <div className="grid lg:grid-cols-2">
          <div data-theme="light" aria-label="light theme" role="region"><Gallery /></div>
          <div data-theme="dark" aria-label="dark theme" role="region"><Gallery /></div>
        </div>
      ) : <Gallery />}
    </div>
  );
}
