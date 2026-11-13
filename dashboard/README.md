# AgentBench-Lite dashboard

A local React + TypeScript + Tailwind app that **displays and requests only**: every number comes from the
AgentBench-Lite API, and the dashboard contains no benchmark, evaluation or failure-analysis logic.

## Run it (two terminals)

```powershell
# terminal 1 - the API (from the repository root)
python scripts/serve_api.py                      # http://127.0.0.1:8000

# terminal 2 - the dashboard
cd dashboard
npm install                                      # first time only (exact versions from package-lock.json)
npm run dev                                      # open http://localhost:5173
```

The API allows browser requests only from `http://localhost:5173` / `http://127.0.0.1:5173` (CORS). If the
API runs elsewhere, create `dashboard/.env.local` with `VITE_API_BASE=http://127.0.0.1:8001`.

## Checks (no server needed)

```powershell
npm run check        # generated types up to date + TypeScript type check + tests
npm run build        # production build into dist/ (git-ignored)
```

## Types come from the API contract

`src/api/schema.d.ts` is GENERATED, never edited by hand:

```powershell
python scripts/export_openapi.py     # (repository root) writes dashboard/openapi.json from the backend
npm run gen:types                    # (dashboard/) openapi.json -> src/api/schema.d.ts
```

If the backend contract changes (deliberately, via `scripts/update_api_contract.py --reason`), a Python test
fails until `openapi.json` is re-exported, `npm run check:types` fails until the types are regenerated, and
TypeScript then shows every place in the dashboard that must follow the change.

## Layout

| Path | What |
|---|---|
| `src/api/client.ts` | the only code that calls the API; one `ApiError` for every failure |
| `src/api/useApi.ts` | a small hook: loading / error / ready state for one request |
| `src/api/schema.d.ts` | generated TypeScript types (from `openapi.json`) |
| `src/pages/` | Runs (`/`, with the pass-rate chart and run selection), compare (`/compare?ids=..`), start a run (`/runs/new`), run job progress (`/jobs/:jobId`), run details (`/suites/:id`), trace viewer (`/suites/:id/runs/:runId`), failures (`/suites/:id/failures`), task history (`/tasks/:taskId`), connection |
| `src/charts/data.ts` | pure functions that only RESHAPE API data for charts (never compute metrics) |
| `src/charts/trend.ts` | pure grouping for the pass-rate chart: six-part key, which runs may be connected, baseline |
| `src/components/TrendChart.tsx` | the pass-rate-over-time chart, its data table, the 500-run note and the scripted toggle |
| `src/components/ui.tsx` | badges (REAL/SCRIPTED, outcome, complete), card, loading/error box |
| `src/format.ts` | display only: UTC times, `n/a` for unknown values, server counts |
| `src/test/` | test setup, a fake `fetch`, and fixtures typed with the contract types |
