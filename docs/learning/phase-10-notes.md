# Phase 10 notes — the React dashboard

## Verified before starting (against the pinned contract)
1. **Trace viewer:** `GET /suites/{suite_id}/runs/{run_id}` exists → `RunDetailOut` with the full trace
   (steps, tool calls with output OR error), final answer, retries, evaluation checks with reasons, and the
   failure analysis (category, signals, warnings with evidence, step indexes, tool names). No change needed.
2. **Pagination:** `GET /suites`, `GET /runs`, `GET /tasks/{id}/history` take `limit` (1–100) and `offset`
   and return `{limit, offset, total, returned, next_offset}`. No change needed.
3. **Pass rate over time:** `SuiteSummaryOut` has `started_at`, `suite_name`, `kind`, `model`, `complete` and
   the server-computed `pass_rate.rate` — the chart plots it as given (no recalculation in the browser).
   **Caveat:** the summary does not say whether a run was a SUBSET (the 2-task pilot would look like a
   full shop-hard score). Options: (A) fetch `/suites/{id}` per point (no change), or (B) add
   `tasks_fingerprint` + `registration_status` to `SuiteSummaryOut` via a deliberate contract update.
   Decide before Step 10.3.

## The concepts (Step 10.1)
| Concept | In plain words |
|---|---|
| Node.js / npm | run JavaScript tools on your computer / install packages (like pip) |
| package.json / package-lock.json | the dashboard's pyproject.toml / the exact version of every package |
| Vite | the dev server on localhost:5173; reloads the page when you save |
| TypeScript | JavaScript with types that are ENFORCED: the build fails on a type mistake |
| React component | a function that returns what to show, written in JSX (HTML inside TypeScript) |
| props / state | data passed IN / data a component REMEMBERS (`useState`) |
| effect | "after showing the page, do this" (`useEffect`), e.g. call the API once |
| Tailwind | styling with small class names (`text-sm font-bold`) |
| generated types | `openapi.json` (from the backend) → `schema.d.ts`: a renamed field becomes a compile error |

## What Step 10.1 built
- `dashboard/` (Vite 5.4.11, React 18.3.1, TypeScript 5.6.3, Tailwind 3.4.15, Vitest 2.1.8, Testing
  Library, openapi-typescript 7.4.4 — exact versions, lock file committed, node_modules ignored).
- `scripts/export_openapi.py` (read-only) → `dashboard/openapi.json` → `npm run gen:types`.
- `client.ts`: one `request()` and one `ApiError` (status, code, message, details) for every failure:
  the API's `{"error": …}` shape, an unreachable API (status 0, with a hint), or an unexpected answer.
- `useApi.ts`: loading / error / ready state with `reload()`.
- The connection page: shows `/health` exactly as reported (status, schema version, real runs).
- Freshness: a Python test checks `openapi.json` matches the backend; `npm run check:types` checks the
  TypeScript types match `openapi.json`.

**Two things TypeScript and the plan caught:** the fake `fetch` in the tests did not declare its second
argument, so reading it was a compile error (fixed in the helper, not hidden); and a test used a package
that was not in the approved list (`user-event`) — replaced with `fireEvent`, already included.

## Self-check (10.1)
1. Why must `schema.d.ts` never be edited by hand?
2. What does the dashboard show when the API is not running, and where does that message come from?
3. Why does the dashboard's code call `fetch` in exactly one file?
4. Why can the browser on localhost:5173 read `/health`, but a page on another site cannot?
