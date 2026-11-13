// The ONLY place that talks to the API. Every response type comes from schema.d.ts, which is generated
// from the backend's pinned OpenAPI contract (npm run gen:types) - never written by hand.
import type { components } from "./schema";

export type Schemas = components["schemas"];
export type Health = Schemas["HealthOut"];
export type Index = Schemas["IndexOut"];
export type ErrorBody = Schemas["ErrorBody"];

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

export const api = {
  health: () => request<Health>("/health"),
  index: () => request<Index>("/"),
};
