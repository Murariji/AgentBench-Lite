import { describe, expect, it } from "vitest";
import { fakeFetch } from "../test/fakeApi";
import { API_BASE, ApiError, api, request } from "./client";

describe("API client", () => {
  it("calls the local API address and returns typed data", async () => {
    const { calls, fetchMock } = fakeFetch({
      "/health": { body: { status: "ok", schema_version: 3, real_runs_enabled: false } },
    });
    const health = await api.health();
    expect(health.schema_version).toBe(3);
    expect(calls).toEqual(["/health"]);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(`${API_BASE}/health`);
    expect(API_BASE).toBe("http://127.0.0.1:8000");
  });

  it("turns the API's error shape into one ApiError", async () => {
    fakeFetch({
      "/suites/zzzz9999": {
        status: 404,
        body: { error: { code: "not_found", message: "no suite id starts with 'zzzz9999'", details: { suite_id: "zzzz9999" } } },
      },
    });
    const error = await request("/suites/zzzz9999").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code: "not_found", details: { suite_id: "zzzz9999" } });
  });

  it("reports an unreachable API as a network error with a hint", async () => {
    fakeFetch({ "/health": "network-down" });
    const error = (await api.health().catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(0);
    expect(error.code).toBe("network_error");
    expect(error.message).toContain("python scripts/serve_api.py");
  });

  it("never trusts an error without the documented shape", async () => {
    fakeFetch({ "/health": { status: 502, raw: "<html>Bad gateway</html>" } });
    const error = (await api.health().catch((e: unknown) => e)) as ApiError;
    expect(error).toMatchObject({ status: 502, code: "unexpected_response" });
  });

  it("sends JSON bodies with the right content type (for POST requests later)", async () => {
    const { fetchMock } = fakeFetch({ "/estimates": { body: { allowed: true } } });
    await request("/estimates", { method: "POST", body: JSON.stringify({ agent: "careful" }) });
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });
});
