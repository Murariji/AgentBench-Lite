// Fake API answers for tests, TYPED with the generated contract types: if one stops matching what the
// real API returns (schema.d.ts), the tests no longer compile. Values mirror real stored runs.
import type { RunDetail, Schemas, SuiteDetail, SuitePage } from "../api/client";

const REAL_ID = "f8e7c26f1a1c48daa40d857ab7842470";
const OLD_ID = "743cde41aaaabbbbccccddddeeeeffff";
const RUN_PASS = "aaaa1111bbbb2222cccc3333dddd4444";
const RUN_FAIL = "eeee5555ffff6666aaaa7777bbbb8888";

const rate = (passed: number, eligible: number): Schemas["Rate"] => ({ passed, eligible });

export const metrics = (overrides: Partial<Schemas["SuiteMetrics"]> = {}): Schemas["SuiteMetrics"] => ({
  scheduled_runs: 2, eligible_runs: 2, passed_runs: 2, failed_runs: 0, infra_errors: 0, skipped_runs: 0,
  complete: true, pass_rate: rate(2, 2), by_difficulty: { hard: rate(2, 2) }, avg_steps: 7, avg_llm_calls: 7,
  avg_input_tokens: 5272, avg_output_tokens: 314, avg_duration_seconds: 44.16, total_llm_calls: 14,
  total_duration_seconds: 88.32, tool_calls: 12, tool_errors: 0, failed_checks: [], k: 1,
  pass_at_k: null, pass_pow_k: null, ...overrides,
});

const summary = (o: Partial<Schemas["SuiteSummaryOut"]>): Schemas["SuiteSummaryOut"] => ({
  suite_id: REAL_ID, short_id: REAL_ID.slice(0, 8), suite_name: "shop-hard", kind: "real", config_name: "gemini-default",
  provider: "gemini", model: "gemini-3.5-flash-lite", repeats: 1, started_at: "2026-11-13T09:34:52.234559Z",
  finished_at: "2026-11-13T09:36:20.558597Z", scheduled_runs: 2, passed: 2, failed: 0, infra_errors: 0, skipped: 0,
  total_llm_calls: 14, pass_rate: { passed: 2, eligible: 2, rate: 1, text: "2/2 (100.0%)" }, complete: true,
  stop_reason: null, tasks_fingerprint: "0d0389d403dc", registration_status: "subset", scope: "subset", ...o,
});

export const suitePage = (o: Partial<SuitePage["pagination"]> = {}): SuitePage => ({
  items: [
    summary({}),
    summary({
      suite_id: OLD_ID, short_id: OLD_ID.slice(0, 8), suite_name: "shop", kind: "scripted", provider: "fake",
      config_name: "sloppy-script", model: "scripted-sloppy-v1", scheduled_runs: 10, passed: 1, failed: 1,
      infra_errors: 1, skipped: 7, complete: false, stop_reason: "quota_exhausted in shop-003",
      pass_rate: { passed: 1, eligible: 2, rate: 0.5, text: "1/2 (50.0%)" }, total_llm_calls: 5,
      tasks_fingerprint: null, registration_status: "unknown", scope: "unknown",     // stored without task definitions
    }),
    summary({
      suite_id: "0af951e0aaaabbbbccccddddeeeeffff", short_id: "0af951e0", suite_name: "shop", scheduled_runs: 30,
      repeats: 3, tasks_fingerprint: "01031dae7fb1", registration_status: "unregistered", scope: "full",
      pass_rate: { passed: 30, eligible: 30, rate: 1, text: "30/30 (100.0%)" },
    }),
    summary({
      suite_id: "dddd0000aaaabbbbccccddddeeeeffff", short_id: "dddd0000", tasks_fingerprint: "34c76a170351",
      registration_status: "differs", scope: "full", kind: "scripted",
    }),
  ],
  pagination: { limit: 20, offset: 0, total: 4, returned: 4, next_offset: null, ...o },
});

const runSummary = (o: Partial<Schemas["RunSummaryOut"]>): Schemas["RunSummaryOut"] => ({
  run_id: RUN_PASS, task_id: "hard-001", repeat: 0, difficulty: "hard", outcome: "passed", status: "completed",
  final_answer: "10995.5", steps: 9, llm_calls: 9, retries: 0, duration_seconds: 61.2, error_kind: null,
  failed_checks: [], ...o,
});

/** The real Stage 1 pilot: a SUBSET of shop-hard v1, complete, retries recorded. */
export const pilotDetail: SuiteDetail = {
  suite_id: REAL_ID, suite_name: "shop-hard", kind: "real",
  config: { name: "gemini-default", provider: "gemini", model: "gemini-3.5-flash-lite", system_prompt: "…",
            max_attempts: 3, min_interval_seconds: 6, prompt_hash: "396a9e3fe29c" },
  config_fingerprint: "dfba9fdfb262", repeats: 1, started_at: "2026-11-13T09:34:52.234559Z",
  finished_at: "2026-11-13T09:36:20.558597Z", dataset: "shop.db sha256:62143ef0c309",
  tools: [{ name: "calculator", version: 2, description: "…", parameters: {} },
          { name: "sql_query", version: 1, description: "…", parameters: {} }],
  tools_fingerprint: "c1af5a87019e", tasks_fingerprint: "0d0389d403dc", request_budget: 25, estimated_requests: 10,
  stop_reason: null, complete: true, metrics: metrics(),
  registration: { status: "subset", problems: [], notes: [], version: 1, suite_fingerprint: "5f106feaff34",
                  line: "SUBSET of shop-hard v1: 2 of 9 tasks, each matching its registered definition - NOT a full-suite result" },
  runs: [runSummary({}), runSummary({ run_id: "cccc9999dddd0000eeee1111ffff2222", task_id: "hard-007", final_answer: "Monday", steps: 5, llm_calls: 5 })],
  skipped: [],
};

/** An older, scripted, INCOMPLETE run: tools and retries not recorded, one failure, skipped runs. */
export const oldDetail: SuiteDetail = {
  ...pilotDetail, suite_id: OLD_ID, suite_name: "shop", kind: "scripted", tools: null, tools_fingerprint: null,
  config: { ...pilotDetail.config, name: "sloppy-script", provider: "fake", model: "scripted-sloppy-v1" },
  request_budget: null, complete: false, stop_reason: "quota_exhausted in shop-003",
  metrics: metrics({ complete: false, infra_errors: 1, skipped_runs: 7, scheduled_runs: 10, pass_rate: rate(1, 2), failed_runs: 1 }),
  registration: { status: "unregistered", line: "shop: not registered (no pre-registration exists for this suite)",
                  problems: [], notes: [], version: null, suite_fingerprint: null },
  runs: [
    runSummary({ run_id: RUN_PASS, task_id: "shop-001", difficulty: "easy", final_answer: "30", steps: 2, llm_calls: 2, retries: null }),
    runSummary({ run_id: RUN_FAIL, task_id: "shop-002", difficulty: "easy", outcome: "failed", final_answer: "0", steps: 2,
                 llm_calls: 2, retries: null, failed_checks: ["answer:number"] }),
    runSummary({ run_id: "1111222233334444555566667777aaaa", task_id: "shop-003", difficulty: "medium", outcome: "infra_error",
                 status: "error", final_answer: null, steps: 0, llm_calls: 1, retries: null, error_kind: "quota_exhausted" }),
  ],
  skipped: [{ task_id: "shop-004", repeat: 0, reason: "quota_exhausted in shop-003" }],
};

/** A failed task run with a SQL step, a calculator error, checks and a failure analysis. */
export const failedRun: RunDetail = {
  suite_id: OLD_ID,
  record: {
    task_id: "shop-003", repeat: 0, difficulty: "medium", outcome: "failed",
    run: {
      run_id: RUN_FAIL, task_id: "shop-003", status: "completed", final_answer: "0", duration_seconds: 0.1,
      error: null, error_kind: null, llm_calls: 3, retries: null,
      trace: { task_id: "shop-003", steps: [
        { index: 0, llm_output: "", timestamp: "2026-11-13T05:09:54Z", input_tokens: null, output_tokens: null,
          tool_call: { tool_name: "sql_query", arguments: { query: "SELECT COUNT(*) FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL" },
                       output: "COUNT(*)\n0\n(1 row)", error: null } },
        { index: 1, llm_output: "", timestamp: "2026-11-13T05:09:55Z", input_tokens: null, output_tokens: null,
          tool_call: { tool_name: "calculator", arguments: { expression: "sqrt(9)" }, output: null,
                       error: "function 'sqrt' is not allowed; allowed: abs, max, min, round" } },
        { index: 2, llm_output: "0", timestamp: "2026-11-13T05:09:56Z", input_tokens: null, output_tokens: null, tool_call: null },
      ] },
    },
    evaluation: { run_id: RUN_FAIL, task_id: "shop-003", passed: false, checks: [
      { name: "status", passed: true, reason: "run completed" },
      { name: "answer:number", passed: false, reason: "found 0 (the only number); expected 3 (difference 3 > allowed 0)" },
    ] },
  },
  analysis: {
    run_id: RUN_FAIL, task_id: "shop-003", repeat: 0, outcome: "failed", category: "wrong_result", retries_recorded: false,
    infra_error_kind: null,
    signals: [{ name: "wrong_result", evidence: "the answer '0' repeats the result of step 0 (sql_query)", step_indexes: [0], tool_names: ["sql_query"] }],
    warnings: [{ name: "unfixed_tool_errors", evidence: "1 tool error(s) never fixed; e.g. step 1: calculator", step_indexes: [1], tool_names: ["calculator"] }],
  },
};

export const ids = { REAL_ID, OLD_ID, RUN_PASS, RUN_FAIL };

// ---------- Step 10.3a: failures, history, measure ----------
const analysis = (o: Partial<Schemas["RunAnalysis"]>): Schemas["RunAnalysis"] => ({
  run_id: "r0000000000000000000000000000000", task_id: "hard-001", repeat: 0, outcome: "passed", category: null,
  retries_recorded: true, infra_error_kind: null, signals: [], warnings: [], ...o,
});

/** Like the stored sloppy shop-hard run, plus one infrastructure error and one near miss. */
export const failuresOut: Schemas["FailuresOut"] = {
  note: "Rule-based, from the stored trace: likely patterns, not the model's reasoning. Infrastructure errors are not agent failures.",
  analysis: {
    suite_id: OLD_ID, failed_runs: 3, passed_runs: 1, infra_errors: 1, skipped_runs: 2, retries_not_recorded: 0,
    category_counts: { wrong_result: 2, unclassified: 1 },
    warning_counts: { near_step_limit: 1 },
    runs: [
      analysis({ run_id: "w1aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", task_id: "hard-001", outcome: "failed", category: "wrong_result",
                 signals: [{ name: "wrong_result", evidence: "the answer '16107' repeats the result of step 0 (sql_query)", step_indexes: [0], tool_names: ["sql_query"] }] }),
      analysis({ run_id: "w2aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", task_id: "hard-003", outcome: "failed", category: "wrong_result",
                 signals: [{ name: "wrong_result", evidence: "the answer '77.8' repeats the result of step 0 (sql_query)", step_indexes: [0], tool_names: ["sql_query"] }] }),
      analysis({ run_id: "u1aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", task_id: "hard-008", outcome: "failed", category: "unclassified",
                 signals: [{ name: "unclassified", evidence: "failed checks: answer:contains; the trace does not show a clear pattern", step_indexes: [], tool_names: [] }] }),
      analysis({ run_id: "p1aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", task_id: "hard-002", outcome: "passed",
                 warnings: [{ name: "near_step_limit", evidence: "used 9 of 10 allowed steps", step_indexes: [8], tool_names: [] }] }),
      analysis({ run_id: "i1aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", task_id: "hard-004", outcome: "infra_error", infra_error_kind: "quota_exhausted",
                 retries_recorded: true }),
    ],
  },
};

const entry = (o: Partial<Schemas["TaskHistoryEntry"]>): Schemas["TaskHistoryEntry"] => ({
  suite_id: REAL_ID, started_at: "2026-11-13T08:38:00Z", config_name: "gemini-default", provider: "gemini",
  model: "gemini-3.5-flash-lite", prompt_hash: "396a9e3fe29c", task_hash: "fb8b608c18bc", repeat: 0, outcome: "passed",
  error_kind: null, llm_calls: 7, duration_seconds: 40, final_answer: "16107", reason: null,
  tools_fingerprint: "c1af5a87019e", tools: null, ...o,
});

/** shop-010 across runs, newest first (as the server sends it). */
export const historyPage = (o: Partial<Schemas["Pagination"]> = {}): Schemas["HistoryPage"] => ({
  task_id: "shop-010",
  items: [
    entry({ suite_id: "sk000000aaaabbbbccccddddeeeeffff", started_at: "2026-11-13T10:00:00Z", outcome: "skipped",
            llm_calls: null, final_answer: null, reason: "budget_exhausted in shop-009", duration_seconds: null }),
    entry({ repeat: 1, outcome: "infra_error", error_kind: "server", llm_calls: 3, final_answer: null }),
    entry({}),
    entry({ suite_id: "0af951e0aaaabbbbccccddddeeeeffff", started_at: "2026-11-13T06:06:00Z", llm_calls: 9,
            tools_fingerprint: null }),
  ],
  pagination: { limit: 20, offset: 0, total: 4, returned: 4, next_offset: null, ...o },
});

export const measureOut: Schemas["MeasureOut"] = {
  task_id: "shop-010",
  groups: [
    { provider: "gemini", model: "gemini-3.5-flash-lite", kind: "real", tools: "unknown", calculator: "unknown",
      suites: 2, scheduled: 4, passed: 4, evaluated: 4, infra_errors: [], skipped: 0, avg_llm_calls: 8.25,
      avg_steps: 7.75, runs_with_round_errors: 3, round_errors: 3, tool_errors: 3, near_step_limit: 4, step_limit_failures: 0 },
    { provider: "gemini", model: "gemini-3.5-flash-lite", kind: "real", tools: "c1af5a87019e", calculator: "calculator v2",
      suites: 1, scheduled: 3, passed: 3, evaluated: 3, infra_errors: ["server"], skipped: 0, avg_llm_calls: 7,
      avg_steps: 7, runs_with_round_errors: 0, round_errors: 0, tool_errors: 0, near_step_limit: 3, step_limit_failures: 0 },
  ],
  limitations: [
    "Tiny samples (4 evaluated, 3 evaluated): exploratory evidence, not statistical proof.",
    "'unknown' = tools were not recorded for those runs; they are not assumed to be any version.",
    "Compare only columns of the SAME agent; scripted columns follow a fixed script (not AI).",
    "A tools change can bundle behaviour AND description changes; the effect is their combination.",
    "Runs on different days can differ for reasons outside our control (the provider's model).",
    "Infrastructure errors and skipped runs are excluded from correctness and averages.",
  ],
};
