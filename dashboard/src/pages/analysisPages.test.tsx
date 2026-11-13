// Step 10.3a: Failures page and Task history page (+ the pure chart-data functions). Fake API only.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../App";
import { categoryBars, historyBars } from "../charts/data";
import { fakeFetch } from "../test/fakeApi";
import { failuresOut, historyPage, ids, measureOut, oldDetail } from "../test/fixtures";

function open(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>);
}

describe("chart data (reshaping only)", () => {
  it("keeps the server's categories, counts and order - nothing added", () => {
    expect(categoryBars({ wrong_result: 2, unclassified: 1 })).toEqual([
      { category: "wrong_result", runs: 2 }, { category: "unclassified", runs: 1 },
    ]);
    expect(categoryBars(undefined)).toEqual([]);
  });

  it("orders history oldest first and keeps 'not run' as null, never 0", () => {
    const bars = historyBars(historyPage().items);
    expect(bars.map((b) => b.outcome)).toEqual(["passed", "passed", "infra_error", "skipped"]);
    expect(bars.map((b) => b.llmCalls)).toEqual([9, 7, 3, null]);
  });
});

describe("Failures page", () => {
  const path = `/suites/${ids.OLD_ID}/failures`;

  it("shows the server's summary, categories, evidence and trace links", async () => {
    fakeFetch({ [path]: { body: failuresOut } });
    open(path);
    expect(await screen.findByText(/likely patterns, not the model's reasoning/)).toBeInTheDocument();
    const data = screen.getByRole("table", { name: "failure categories (data)" });     // the accessible table
    expect(within(data).getAllByRole("row").map((r) => r.textContent)).toEqual(
      ["CategoryFailed runs", "wrong_result2", "unclassified1"]);
    expect(screen.getByRole("img", { name: "Failure categories: wrong_result 2, unclassified 1." })).toBeInTheDocument();
    expect(screen.getAllByText(/repeats the result of step 0 \(sql_query\)/, { selector: "li" })).toHaveLength(2); // both runs' evidence
    expect(screen.getByRole("link", { name: "hard-003" })).toHaveAttribute("href", `/suites/${ids.OLD_ID}/runs/w2aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`);
  });

  it("keeps infrastructure errors apart from agent failures", async () => {
    fakeFetch({ [path]: { body: failuresOut } });
    open(path);
    const infra = (await screen.findByText("Infrastructure errors (NOT agent failures)")).closest("section")!;
    expect(infra).toHaveTextContent("hard-004");
    expect(infra).toHaveTextContent("quota_exhausted");
    const categories = screen.getByRole("table", { name: "failure categories (data)" });
    expect(categories).not.toHaveTextContent("infra");                                  // never a failure category
    expect(screen.getByText("Infra errors (not failures)").nextSibling).toHaveTextContent("1");
  });

  it("lists near misses separately, as warnings only", async () => {
    fakeFetch({ [path]: { body: failuresOut } });
    open(path);
    const near = (await screen.findByText(/Near misses \(warnings only/)).closest("section")!;
    expect(near).toHaveTextContent("near_step_limit");
    expect(near).toHaveTextContent("used 9 of 10 allowed steps");
  });

  it("says so when there are no failures", async () => {
    fakeFetch({ [path]: { body: { ...failuresOut, analysis: { ...failuresOut.analysis, category_counts: {}, runs: [], warning_counts: {}, infra_errors: 0, failed_runs: 0 } } } });
    open(path);
    expect(await screen.findAllByText("No agent failures in this run.")).toHaveLength(1);
  });

  it("shows the API's 409 for a run without task definitions", async () => {
    fakeFetch({ [path]: { status: 409, body: { error: { code: "not_analysable", message: "this suite stored no task definitions", details: null } } } });
    open(path);
    expect(await screen.findByRole("alert")).toHaveTextContent("not_analysable");
  });

  it("is linked from the run details page", async () => {
    fakeFetch({ [`/suites/${ids.OLD_ID}`]: { body: oldDetail } });
    open(`/suites/${ids.OLD_ID}`);
    expect(await screen.findByRole("link", { name: "Failure analysis →" })).toHaveAttribute("href", path);
    expect(screen.getByRole("link", { name: "shop-002" })).toHaveAttribute("href", "/tasks/shop-002");
  });
});

describe("Task history page", () => {
  const replies = (page = historyPage()) => ({
    "/tasks/shop-010/history?limit=20&offset=0": { body: page },
    "/tasks/shop-010/measure": { body: measureOut },
  });

  it("shows every run with honest labels and an accessible chart summary", async () => {
    fakeFetch(replies());
    open("/tasks/shop-010");
    const table = await screen.findByRole("table", { name: "task history" });
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("skipped");
    expect(rows[1]).toHaveTextContent("budget_exhausted in shop-009");
    expect(rows[2]).toHaveTextContent("infra error");
    expect(rows[4]).toHaveTextContent("unknown");                                       // tools not recorded
    expect(screen.getByRole("img", { name: /LLM calls per run, oldest first: .* skipped not run\./ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "0af951e0" })).toHaveAttribute("href", "/suites/0af951e0aaaabbbbccccddddeeeeffff");
  });

  it("shows the measure exactly as the server reports it, with ALL limitations", async () => {
    fakeFetch(replies());
    open("/tasks/shop-010");
    const measure = await screen.findByRole("table", { name: "measure by agent and tools" });
    expect(measure).toHaveTextContent("unknown (not recorded)");
    expect(measure).toHaveTextContent("c1af5a87 (calculator v2)");
    expect(measure).toHaveTextContent("8.25");                                          // the server's average
    expect(measure).toHaveTextContent("1 (server)");                                    // infra apart, with its kind
    const note = screen.getByRole("note");
    expect(within(note).getAllByRole("listitem")).toHaveLength(measureOut.limitations.length);
    expect(note).toHaveTextContent("not statistical proof");
  });

  it("pages through history with the server's offsets", async () => {
    const { calls } = fakeFetch({
      ...replies(historyPage({ total: 24, next_offset: 20 })),
      "/tasks/shop-010/history?limit=20&offset=20": { body: historyPage({ offset: 20, total: 24, next_offset: null }) },
    });
    open("/tasks/shop-010");
    fireEvent.click(await screen.findByRole("button", { name: "Next" }));
    expect(await screen.findByText("21–24 of 24")).toBeInTheDocument();
    expect(calls).toContain("/tasks/shop-010/history?limit=20&offset=20");
  });

  it("shows the API's 404 for an unknown task", async () => {
    fakeFetch({
      "/tasks/nope-1/history?limit=20&offset=0": { status: 404, body: { error: { code: "not_found", message: "unknown task 'nope-1'", details: null } } },
      "/tasks/nope-1/measure": { status: 404, body: { error: { code: "not_found", message: "unknown task 'nope-1'", details: null } } },
    });
    open("/tasks/nope-1");
    expect((await screen.findAllByRole("alert"))[0]).toHaveTextContent("unknown task 'nope-1'");
  });
});
