// Step 10.1: is the dashboard connected to the API? Shows GET /health, exactly as the server reports it.
import { API_BASE, api } from "../api/client";
import { useApi } from "../api/useApi";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-6 border-b border-border py-2 last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  );
}

export function ConnectionPage() {
  const health = useApi(api.health);

  return (
    <section className="mx-auto max-w-xl rounded-lg border border-border bg-surface p-6 shadow-sm">
      <h2 className="mb-1 text-title">API connection</h2>
      <p className="mb-4 text-sm text-muted">
        The dashboard only displays what the API returns. Address: <code>{API_BASE}</code>
      </p>

      {health.status === "loading" && <p role="status">Connecting…</p>}

      {health.status === "error" && (
        <div role="alert" className="rounded border border-danger-fg/30 bg-danger-bg p-3 text-sm text-danger-fg">
          <p className="font-semibold">Not connected ({health.error.code})</p>
          <p className="mt-1">{health.error.message}</p>
          <button onClick={health.reload} className="mt-3 rounded bg-danger-solid px-3 py-1 text-on-danger hover:bg-danger-solid/90">
            Try again
          </button>
        </div>
      )}

      {health.status === "ready" && (
        <>
          <p role="status" className="mb-3 inline-block rounded bg-success-bg px-2 py-0.5 text-sm text-success-fg">
            Connected
          </p>
          <dl className="text-sm">
            <Row label="Status">{health.data.status}</Row>
            <Row label="Results database schema">version {health.data.schema_version}</Row>
            <Row label="Real Gemini runs">
              {health.data.real_runs_enabled ? (
                <span className="rounded bg-warning-bg px-2 py-0.5 text-warning-fg">ENABLED on this server</span>
              ) : (
                <span className="rounded bg-surface-2 px-2 py-0.5 text-muted">disabled (scripted runs only)</span>
              )}
            </Row>
          </dl>
          <button onClick={health.reload} className="mt-4 text-sm text-muted underline hover:text-fg">
            Check again
          </button>
        </>
      )}
    </section>
  );
}
