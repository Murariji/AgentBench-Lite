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
| `src/pages/` | pages (Step 10.1: the API connection page) |
| `src/test/` | test setup and a fake `fetch` (tests never call a server) |
