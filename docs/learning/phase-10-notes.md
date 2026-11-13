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

## Step 10.2 — pages and URLs

| Concept | In plain words |
|---|---|
| routing | the URL picks the page (`/suites/42daa8df`) without reloading the app; back button works |
| URL parameter | `:suiteId` in `/suites/:suiteId`, read with `useParams()` |
| query string | page + filter in the URL (`/?offset=20&real_only=true`), read with `useSearchParams()` |
| dependencies | `useApi(load, [suiteId])` loads again when the suite id changes |
| typed fixtures | the fake API answers in tests use the contract types: a mismatch does not compile |

**Display only:** the run list shows the server's pass-rate text; the details page shows the server's
counts ("9 / 9") and computes no percentage; unknown values show as "n/a" or "not recorded", never 0.

**A contract detail TypeScript found:** fields with defaults on the backend (`signals`, `trace.steps`,
`arguments`…) are OPTIONAL in the contract. The API always sends them, but the dashboard must not rely on
more than the contract promises, so a missing list is treated as empty.

## Self-check (10.2)
5. Why are the page offset and the "real only" filter kept in the URL?
6. Why does the details page show "2 / 2" instead of "100%"?
7. What does the Runs page show for a run with an infrastructure error, and why is it not a failure?
8. Why must the test fixtures be typed with the generated contract types?

## Requirements recorded for Step 10.3b (user, before 10.3a)
1. Chart comparability: only `registration_status = matches` runs form the full-suite trend; subset,
   differs and unregistered runs are separate markers, never connected; never one line across different
   models, agent configurations or tool fingerprints; incomplete runs visibly distinguished and not
   connected unless their comparability is established.
2. API values: the server's `pass_rate.rate` unchanged; null stays a gap (never 0%); verify the needed fields
   exist in GET /suites; no metric calculated in React.
3. Pagination: follow `next_offset` up to 500 runs; if the limit is reached, say visibly that the chart shows
   only the latest 500 runs.

**Verified against the contract:** GET /suites has registration_status, provider, model, complete,
pass_rate.rate and pagination — but NOT a config fingerprint (only `config_name`, a label) and NOT
`tools_fingerprint`. 10.3b therefore needs a decision: a deliberate contract change adding
`config_fingerprint` + `tools_fingerprint` to SuiteSummaryOut, or fetching run details per point.
Consequence of rule 1: unregistered suites (e.g. all Gemini `shop` runs) never form a trend line.

## Step 10.3a — Failures and Task history

| Concept | In plain words |
|---|---|
| Recharts | charts as components: `<BarChart data={rows}><XAxis dataKey="category" /><Bar dataKey="runs" /></BarChart>` |
| reshaping vs recalculating | `{"wrong_result": 4}` → `[{category: "wrong_result", runs: 4}]` is reshaping (same numbers); a percentage from raw outcomes would be recalculating — never done |
| pure function | same input → same output, nothing else happens; easy to test on its own |
| bars, not lines, for history | separate runs are separate events; a line would suggest a smooth change between them |
| accessible charts | an `aria-label` summary and a data table with the same values next to every chart |

**Honesty in these pages:** infrastructure errors have their own section and never appear in the failure
chart; near misses are labelled "warnings only"; skipped runs have no bar (not a 0 bar); tools "unknown"
stays unknown; the measure always shows every limitation.

**A lesson about sabotage checks:** the first sabotage did not change the file (square brackets are special
in `sed` patterns), so it "passed" for the wrong reason. A sabotage check is only valid if you confirm the
code really changed.

## Step 10.3b — Compare page and pass-rate chart

| Concept | In plain words |
|---|---|
| one formula | the list and the details page call the SAME fingerprint function, so they can never disagree |
| grouping key | six parts (suite, provider, model, config, tools, real/scripted); a line only joins runs with all six equal |
| unknown is not a value | a missing tools fingerprint gets its own group, written differently from any real fingerprint |
| independent lines | each group is sorted by time on its own; a run from another group can never sit "between" its points |
| baseline vs trend | one point is a starting measurement, not a direction; we say "baseline" |
| scaling vs computing | turning 0.78 into a dot's height is drawing; turning outcomes into 0.78 is computing — only the server computes |
| pagination | ask for 100 runs at a time and follow `next_offset`, stopping at 500 and saying so |

**Why today's chart has no line:** the pilot is a subset, the `shop` runs are unregistered, and the
`matches` runs are scripted (hidden by default). The chart says this instead of drawing a misleading line.

## Step 10.4 — Starting a run from the dashboard

| Concept | In plain words |
|---|---|
| estimate before start | like getting the bill before you order: POST /estimates never sends anything to a model |
| the server is the guard | the page never decides if a run is safe; it shows the server's yes/no and its reasons |
| stale estimate | if you change the form after estimating, the old estimate no longer describes your request |
| polling | asking "are you done yet?" every second, and stopping as soon as the answer is yes |
| job vs result | the job's progress lives in the server's memory (lost on restart); the results are saved in SQLite |

## Redesign R1 — themes and base components

| Concept | In plain words |
|---|---|
| design token | a named colour ("surface") whose value depends on the theme; components only use the names |
| preference vs resolved | what you chose (Light/Dark/System) vs what is drawn (light/dark) |
| persistence | the choice is saved in the browser (localStorage); if that is blocked, System is used |
| no flash | a tiny script in index.html sets the theme before anything is drawn |
| context | a value shared with every component below a provider, read with useTheme() |
| WCAG contrast | a number from 1 to 21; text needs 4.5:1 - a test checks every pair in both themes |
| dev-only code | `import.meta.env.DEV` is false in production builds, so the /design page is removed |

## Redesign R2–R6 — shell, Overview, live progress

| Concept | In plain words |
|---|---|
| code splitting | each page is its own small file, downloaded only when you open it |
| app shell | the parts that never change (sidebar, top bar); only the middle changes per page |
| polling + clock | the page asks the server every second; the elapsed clock is just "now minus started_at" |
| counting behind the budget | the request counter sits after the budget check, so it can never disagree with the hard cap |

## Self-check (10.3a)
9. Why are infrastructure errors not a bar in the failure-category chart?
10. A skipped run has `llm_calls: null`. Why is it drawn as no bar instead of a 0 bar?
11. Why does the task-history chart use bars, not a line?
12. Why does every chart have a table next to it?

## Self-check (10.3b)
13. Two runs have the same model but different config fingerprints. Why are they two lines?
14. Why is a run whose tools were not recorded never put on the line of a known tools fingerprint?
15. A run evaluated 0 tasks (rate null). Why is it not drawn at 0%?
16. Why does one comparable run say "baseline" and not "trend"?

## Self-check (10.4)
17. Why can the dashboard not start a real run by itself, even if the page has a bug?
18. Why is the Start button disabled after you change the repeats?
19. What does the job page do when the server says "finished"?

## Self-check (R1)
20. Why do components say `bg-surface` instead of `bg-white`?
21. What would a dark-mode user see without the script in index.html?
22. Why is an unavailable metric shown as "Not available" and not 0?
23. How do we know /design is not in the production build?
