// The ONLY place that talks to the API. Every response type comes from schema.d.ts, which is generated
// from the backend's pinned OpenAPI contract (npm run gen:types) - never written by hand.
import type { components } from "./schema";

export type Schemas = components["schemas"];
export type Health = Schemas["HealthOut"];
export type Index = Schemas["IndexOut"];
export type ErrorBody = Schemas["ErrorBody"];
export type SuitePage = Schemas["SuitePage"];
export type SuiteSummary = Schemas["SuiteSummaryOut"];
export type SuiteDetail = Schemas["SuiteDetailOut"];
export type RunSummary = Schemas["RunSummaryOut"];
export type RunDetail = Schemas["RunDetailOut"];
export type Rate = Schemas["Rate"];
export type Signal = Schemas["Signal"];
export type Failures = Schemas["FailuresOut"];
export type RunAnalysis = Schemas["RunAnalysis"];
export type HistoryPage = Schemas["HistoryPage"];
export type HistoryEntry = Schemas["TaskHistoryEntry"];
export type Measure = Schemas["MeasureOut"];

// Where the API runs. Override with VITE_API_BASE in dashboard/.env.local if you changed the port.
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

/** Every failure becomes ONE error type, mirroring the backend's {"error": {code, message, details}}. */
export class ApiError extends Error {
  constructor(
    public readonly status: number, // HTTP status; 0 = the API could not be reached at all
    public readonly code: string,
    message: string,
    public readonly details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isErrorBody(value: unknown): value is { error: ErrorBody } {
  const error = (value as { error?: unknown } | null)?.error as Partial<ErrorBody> | undefined;
  return typeof error?.code === "string" && typeof error.message === "string";
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}) },
    });
  } catch {
    // Network failure, server not running, or the browser blocked the response (CORS).
    throw new ApiError(0, "network_error",
      `Cannot reach the API at ${API_BASE}. Is it running? (python scripts/serve_api.py)`);
  }
  const text = await response.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null; // not JSON (should not happen with our API) - handled below
  }
  if (!response.ok) {
    if (isErrorBody(body)) {
      throw new ApiError(response.status, body.error.code, body.error.message, body.error.details);
    }
    throw new ApiError(response.status, "unexpected_response",
      `The API answered ${response.status} without the usual error format.`);
  }
  return body as T;
}

export const PAGE_SIZE = 20;

export const api = {
  health: () => request<Health>("/health"),
  index: () => request<Index>("/"),
  /** GET /suites - newest first, paginated by the server (limit/offset). */
  suites: ({ offset = 0, limit = PAGE_SIZE, realOnly = false } = {}) => {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (realOnly) query.set("real_only", "true");
    return request<SuitePage>(`/suites?${query}`);
  },
  suite: (suiteId: string) => request<SuiteDetail>(`/suites/${encodeURIComponent(suiteId)}`),
  run: (suiteId: string, runId: string) =>
    request<RunDetail>(`/suites/${encodeURIComponent(suiteId)}/runs/${encodeURIComponent(runId)}`),
  failures: (suiteId: string) => request<Failures>(`/suites/${encodeURIComponent(suiteId)}/failures`),
  /** GET /tasks/{id}/history - newest suite first, paginated by the server. */
  history: (taskId: string, { offset = 0, limit = PAGE_SIZE } = {}) =>
    request<HistoryPage>(`/tasks/${encodeURIComponent(taskId)}/history?${new URLSearchParams({
      limit: String(limit), offset: String(offset) })}`),
  measure: (taskId: string) => request<Measure>(`/tasks/${encodeURIComponent(taskId)}/measure`),
};
