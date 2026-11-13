// Step 10.1: is the dashboard connected to the API? Shows GET /health, exactly as the server reports it.
import { API_BASE, api } from "../api/client";
import { useApi } from "../api/useApi";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-6 border-b border-slate-100 py-2 last:border-0">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  );
}

export function ConnectionPage() {
  const health = useApi(api.health);

  return (
    <section className="mx-auto max-w-xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-1 text-lg font-semibold">API connection</h2>
      <p className="mb-4 text-sm text-slate-500">
        The dashboard only displays what the API returns. Address: <code>{API_BASE}</code>
      </p>

      {health.status === "loading" && <p role="status">Connecting…</p>}

      {health.status === "error" && (
        <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <p className="font-semibold">Not connected ({health.error.code})</p>
          <p className="mt-1">{health.error.message}</p>
          <button onClick={health.reload} className="mt-3 rounded bg-red-700 px-3 py-1 text-white hover:bg-red-800">
            Try again
          </button>
        </div>
      )}

      {health.status === "ready" && (
        <>
          <p role="status" className="mb-3 inline-block rounded bg-emerald-100 px-2 py-0.5 text-sm text-emerald-800">
            Connected
          </p>
          <dl className="text-sm">
            <Row label="Status">{health.data.status}</Row>
            <Row label="Results database schema">version {health.data.schema_version}</Row>
            <Row label="Real Gemini runs">
              {health.data.real_runs_enabled ? (
                <span className="rounded bg-amber-100 px-2 py-0.5 text-amber-900">ENABLED on this server</span>
              ) : (
                <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-700">disabled (scripted runs only)</span>
              )}
            </Row>
          </dl>
          <button onClick={health.reload} className="mt-4 text-sm text-slate-600 underline hover:text-slate-900">
            Check again
          </button>
        </>
      )}
    </section>
  );
}
