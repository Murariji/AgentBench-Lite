// Step 10.2: runs list, run details, trace viewer - rendered through the REAL routes (MemoryRouter) with a
// fake API. No server, no network.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../App";
import { fakeFetch } from "../test/fakeApi";
import { failedRun, ids, oldDetail, pilotDetail, suitePage } from "../test/fixtures";

const CHART = "/suites?limit=100&offset=0";   // the pass-rate chart reads runs too

function open(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>);
}

describe("Runs page", () => {
  it("lists runs as the API reports them, with honest labels", async () => {
    fakeFetch({ "/suites?limit=20&offset=0": { body: suitePage() }, [CHART]: { body: suitePage() } });
    open("/");
    const table = await screen.findByRole("table", { name: "runs" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(5); // header + 4 runs
    expect(rows[1]).toHaveTextContent("f8e7c26f");
    expect(rows[1]).toHaveTextContent("REAL LLM");
    expect(rows[1]).toHaveTextContent("2/2 (100.0%)"); // the server's own text, not recomputed
    expect(rows[1]).toHaveTextContent("2026-11-13 09:34 UTC");
    expect(rows[2]).toHaveTextContent("SCRIPTED");
    expect(rows[2]).toHaveTextContent("INCOMPLETE");
    expect(rows[2]).toHaveTextContent("1 infra, 7 skipped");
  });

  it("marks subset, full, unknown and differing runs as the API reports them", async () => {
    fakeFetch({ "/suites?limit=20&offset=0": { body: suitePage() }, [CHART]: { body: suitePage() } });
    open("/");
    const rows = within(await screen.findByRole("table", { name: "runs" })).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("SUBSET");            // the 2-task pilot: not a full-suite score
    expect(rows[1]).toHaveTextContent("registered ✓");
    expect(rows[2]).toHaveTextContent("task set unknown");  // never shown as a full run
    expect(rows[2]).not.toHaveTextContent("full suite");
    expect(rows[3]).toHaveTextContent("full suite");
    expect(rows[3]).not.toHaveTextContent("SUBSET");
    expect(rows[4]).toHaveTextContent("DIFFERS from registration");
  });

  it("pages with the server's limit/offset and keeps the page in the URL", async () => {
    const { calls } = fakeFetch({
      [CHART]: { body: suitePage() },
      "/suites?limit=20&offset=0": { body: suitePage({ total: 25, next_offset: 20 }) },
      "/suites?limit=20&offset=20": { body: suitePage({ offset: 20, total: 25, returned: 4, next_offset: null }) },
    });
    open("/");
    fireEvent.click(await screen.findByRole("button", { name: "Next" }));
    expect(await screen.findByText("21–24 of 25")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled(); // next_offset: null = last page
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(await screen.findByText("1–4 of 25")).toBeInTheDocument();
    expect(calls.filter((c) => c !== CHART)).toEqual(
      ["/suites?limit=20&offset=0", "/suites?limit=20&offset=20", "/suites?limit=20&offset=0"]);
  });

  it("asks the server for real runs only (the filter is applied by the API)", async () => {
    const { calls } = fakeFetch({
      [CHART]: { body: suitePage() },
      "/suites?limit=20&offset=0": { body: suitePage() },
      "/suites?limit=20&offset=0&real_only=true": { body: { items: [], pagination: { limit: 20, offset: 0, total: 0, returned: 0, next_offset: null } } },
    });
    open("/");
    fireEvent.click(await screen.findByRole("checkbox", { name: "Real LLM runs only" }));
    expect(await screen.findByText("No real LLM runs stored yet.")).toBeInTheDocument();
    expect(calls).toContain("/suites?limit=20&offset=0&real_only=true");
  });

  it("shows the API's error and can retry", async () => {
    const broken = { status: 503, body: { error: { code: "storage_unavailable", message: "database broken", details: null } } };
    fakeFetch({ "/suites?limit=20&offset=0": broken, [CHART]: broken });
    open("/");
    const alerts = await screen.findAllByRole("alert");                 // the chart and the table both say so
    expect(alerts.every((a) => a.textContent?.includes("Could not load (storage_unavailable)"))).toBe(true);
  });
});

describe("Run details page", () => {
  it("shows the pilot as a SUBSET with the server's counts", async () => {
    fakeFetch({ [`/suites/${ids.REAL_ID}`]: { body: pilotDetail } });
    open(`/suites/${ids.REAL_ID}`);
    const banner = await screen.findByTestId("registration");
    expect(banner).toHaveTextContent("registration: subset");
    expect(banner).toHaveTextContent("NOT a full-suite result");
    expect(screen.getByText("Passed / evaluated").nextSibling).toHaveTextContent("2 / 2"); // counts, no % computed
    expect(screen.getByText("calculator v2, sql_query v1")).toBeInTheDocument();
    expect(screen.getByText("budget 25")).toBeInTheDocument();
    expect(screen.queryByText(/SCRIPTED agent/)).not.toBeInTheDocument();
  });

  it("is honest about scripted, incomplete, unrecorded and skipped", async () => {
    fakeFetch({ [`/suites/${ids.OLD_ID}`]: { body: oldDetail } });
    open(`/suites/${ids.OLD_ID}`);
    expect(await screen.findByText(/SCRIPTED agent: fixed answers written in advance/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("1 infrastructure error(s) and 7 skipped run(s) are NOT counted");
    expect(screen.getByText("not recorded (run stored before tool versions existed)")).toBeInTheDocument();
    expect(screen.getAllByText("not recorded")).toHaveLength(3); // retries: unknown, never shown as 0
    expect(screen.getByText("answer:number")).toBeInTheDocument();
    expect(screen.getByText("infra error")).toBeInTheDocument();
    expect(screen.getByText(/Skipped \(never run\): shop-004/)).toBeInTheDocument();
  });

  it("links every task run to its trace", async () => {
    fakeFetch({ [`/suites/${ids.OLD_ID}`]: { body: oldDetail } });
    open(`/suites/${ids.OLD_ID}`);
    const links = await screen.findAllByRole("link", { name: "trace →" });
    expect(links[1]).toHaveAttribute("href", `/suites/${ids.OLD_ID}/runs/${ids.RUN_FAIL}`);
  });

  it("shows 404 from the API clearly", async () => {
    fakeFetch({ "/suites/zzzz9999": { status: 404, body: { error: { code: "not_found", message: "no suite id starts with 'zzzz9999'", details: null } } } });
    open("/suites/zzzz9999");
    expect(await screen.findByRole("alert")).toHaveTextContent("no suite id starts with 'zzzz9999'");
  });
});

describe("Trace viewer", () => {
  it("shows every step, the SQL, outputs and errors, checks and the analysis", async () => {
    fakeFetch({ [`/suites/${ids.OLD_ID}/runs/${ids.RUN_FAIL}`]: { body: failedRun } });
    open(`/suites/${ids.OLD_ID}/runs/${ids.RUN_FAIL}`);
    const step0 = await screen.findByTestId("step-0");
    expect(step0).toHaveTextContent("sql_query");
    expect(step0).toHaveTextContent("SELECT COUNT(*) FROM customers c JOIN orders o");
    expect(step0).toHaveTextContent("(1 row)");
    expect(within(screen.getByTestId("step-1")).getByRole("note")).toHaveTextContent("function 'sqrt' is not allowed");
    expect(screen.getByText(/expected 3 \(difference 3 > allowed 0\)/)).toBeInTheDocument();
    expect(screen.getByText("wrong_result")).toBeInTheDocument();
    expect(screen.getByText(/likely patterns, not the model's reasoning/)).toBeInTheDocument();
    expect(screen.getByText("unfixed_tool_errors")).toBeInTheDocument();
    expect(screen.getByText(/Retries: not recorded for this run/)).toBeInTheDocument();
  });

  it("does not analyse infrastructure errors as agent failures", async () => {
    const infra = { ...failedRun, record: { ...failedRun.record, outcome: "infra_error" as const },
                    analysis: { ...failedRun.analysis!, category: null, infra_error_kind: "quota_exhausted", signals: [], warnings: [] } };
    fakeFetch({ [`/suites/${ids.OLD_ID}/runs/${ids.RUN_FAIL}`]: { body: infra } });
    open(`/suites/${ids.OLD_ID}/runs/${ids.RUN_FAIL}`);
    expect(await screen.findByText(/Infrastructure error \(quota_exhausted\): not an agent failure/)).toBeInTheDocument();
  });
});

describe("navigation", () => {
  it("has a not-found page and keeps the connection page reachable", async () => {
    fakeFetch({ "/health": { body: { status: "ok", schema_version: 3, real_runs_enabled: false } } });
    open("/no/such/page");
    expect(screen.getByRole("alert")).toHaveTextContent("Page not found");
    fireEvent.click(screen.getByRole("link", { name: "API connection" }));
    expect(await screen.findByText("Connected")).toBeInTheDocument();
  });
});
