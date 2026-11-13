// Step 10.3b: the chart on the Runs page, run selection, and the Compare page. Fake API only.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../App";
import { fakeFetch } from "../test/fakeApi";
import { compareOut, suitePage, summary } from "../test/fixtures";
import { compareBlocker } from "./RunsPage";

const CHART = "/suites?limit=100&offset=0";
const LIST = "/suites?limit=20&offset=0";
const open = (path: string) => render(<MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>);
const page = (items: ReturnType<typeof summary>[], pg = {}) =>
  ({ items, pagination: { limit: 100, offset: 0, total: items.length, returned: items.length, next_offset: null, ...pg } });
const full = (id: string, day: number, o = {}) => summary({
  suite_id: `${id}${"0".repeat(32 - id.length)}`, short_id: id, started_at: `2026-11-${String(day).padStart(2, "0")}T10:00:00Z`,
  registration_status: "matches", scope: "full", complete: true, ...o,
});

describe("pass-rate chart", () => {
  it("says honestly when no run is comparable yet (today's real data)", async () => {
    fakeFetch({ [LIST]: { body: suitePage() }, [CHART]: { body: suitePage() } });   // a subset + unknown runs
    open("/runs");
    expect(await screen.findByText(/No comparable full-suite runs yet/)).toBeInTheDocument();
    expect(screen.getByText(/whether a given run qualifies is known only after it has run/)).toBeInTheDocument();
    const data = screen.getByRole("table", { name: "pass rate over time (data)" });
    expect(data).toHaveTextContent("no - subset (not a full-suite score)");
    expect(data).toHaveTextContent("no - unregistered suite");            // the real shop run
    expect(data).not.toHaveTextContent("no - incomplete");                // the incomplete run is SCRIPTED: hidden
    expect(screen.getByText("2 scripted run(s) hidden.")).toBeInTheDocument();
  });

  it("calls one comparable run a baseline, not a trend", async () => {
    fakeFetch({ [LIST]: { body: suitePage() }, [CHART]: { body: page([full("aaaa0001", 1)]) } });
    open("/runs");
    expect(await screen.findByText(/one run shows a first comparable full-suite baseline, not a trend/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /first comparable full-suite baseline/ })).toBeInTheDocument();
  });

  it("shows the server's text, never 0% for a null rate", async () => {
    const none = full("nnnn0001", 2, { pass_rate: { passed: 0, eligible: 0, rate: null, text: "0/0 (n/a)" } });
    fakeFetch({ [LIST]: { body: suitePage() }, [CHART]: { body: page([full("aaaa0001", 1), none]) } });
    open("/runs");
    const data = await screen.findByRole("table", { name: "pass rate over time (data)" });
    expect(data).toHaveTextContent("2/2 (100.0%)");
    expect(data).not.toHaveTextContent("nnnn0001");
    expect(screen.getByText(/Not plotted .* never shown as 0%\): nnnn0001/)).toBeInTheDocument();
  });

  it("follows next_offset and discloses the 500-run cap", async () => {
    const pageOf = (start: number) => Array.from({ length: 100 }, (_, i) => full(`p${String(start + i).padStart(7, "0")}`, 1));
    const replies: Record<string, { body: unknown }> = { [LIST]: { body: suitePage() } };
    for (let k = 0; k < 5; k++) {
      replies[`/suites?limit=100&offset=${k * 100}`] = {
        body: page(pageOf(k * 100), { offset: k * 100, total: 640, returned: 100, next_offset: (k + 1) * 100 }) };
    }
    const { calls } = fakeFetch(replies);
    open("/runs");
    expect(await screen.findByText("Showing only the latest 500 of 640 runs.")).toBeInTheDocument();
    expect(calls.filter((c) => c.startsWith("/suites?limit=100"))).toHaveLength(5);       // stopped at 500
  });

  it("shows scripted runs only when asked", async () => {
    const scripted = full("ssss0001", 1, { kind: "scripted", provider: "fake", model: "scripted-careful-v1" });
    fakeFetch({ [LIST]: { body: suitePage() }, [CHART]: { body: page([scripted]) } });
    open("/runs");
    expect(await screen.findByText("1 scripted run(s) hidden.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: /Include SCRIPTED runs/ }));
    expect(await screen.findByRole("table", { name: "pass rate over time (data)" })).toHaveTextContent("SCRIPTED scripted-careful-v1");
  });
});

describe("choosing runs to compare", () => {
  it("allows 2-5 runs of ONE suite (the server still checks)", () => {
    expect(compareBlocker(new Map())).toMatch(/select 2 to 5/);
    expect(compareBlocker(new Map([["a", "shop"], ["b", "shop"]]))).toBeNull();
    expect(compareBlocker(new Map([["a", "shop"], ["b", "shop-hard"]]))).toMatch(/different suites cannot be compared \(shop, shop-hard\)/);
    expect(compareBlocker(new Map(["a", "b", "c", "d", "e", "f"].map((k) => [k, "shop"])))).toMatch(/at most 5/);
  });

  it("disables Compare for different suites and opens the page for one suite", async () => {
    fakeFetch({ [LIST]: { body: suitePage() }, [CHART]: { body: suitePage() },
                "/compare?ids=0af951e0aaaabbbbccccddddeeeeffff&ids=743cde41aaaabbbbccccddddeeeeffff": { body: compareOut() } });
    open("/runs");
    const table = await screen.findByRole("table", { name: "runs" });
    const button = screen.getByRole("button", { name: /Compare \(/ });
    fireEvent.click(within(table).getByRole("checkbox", { name: "select f8e7c26f for comparison" }));    // shop-hard
    fireEvent.click(within(table).getByRole("checkbox", { name: "select 0af951e0 for comparison" }));    // shop
    expect(button).toBeDisabled();
    expect(screen.getByTestId("compare-hint")).toHaveTextContent("different suites");
    fireEvent.click(within(table).getByRole("checkbox", { name: "select f8e7c26f for comparison" }));
    fireEvent.click(within(table).getByRole("checkbox", { name: "select 743cde41 for comparison" }));    // shop
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(await screen.findByTestId("fairness")).toHaveTextContent("NOT A FAIR COMPARISON");
  });
});

describe("Compare page", () => {
  const url = "/compare?ids=0af951e0aaaabbbbccccddddeeeeffff&ids=743cde41aaaabbbbccccddddeeeeffff";

  it("shows the server's fairness verdict and conclusions word for word", async () => {
    fakeFetch({ [url]: { body: compareOut() } });
    open(url);
    expect(await screen.findByTestId("fairness")).toHaveTextContent("NOT A FAIR COMPARISON these differ: repeats");
    const lines = within(screen.getByRole("list", { name: "conclusions" })).getAllByRole("listitem");
    expect(lines.map((l) => l.textContent)).toEqual(compareOut().conclusions);
    expect(screen.getByText(/not recorded for at least one run, so they are NOT assumed to be the same/)).toBeInTheDocument();
  });

  it("highlights differing dimensions and tasks, and shows unknown tools honestly", async () => {
    fakeFetch({ [url]: { body: compareOut() } });
    open(url);
    const dims = await screen.findByRole("table", { name: "dimensions" });
    const row = (label: string) => within(dims).getByText(label).closest("tr")!;
    expect(row("repeats")).toHaveAttribute("data-differs", "true");
    expect(row("model")).toHaveAttribute("data-differs", "false");
    expect(within(row("tools (fingerprint)")).getAllByText("not recorded")).toHaveLength(2);
    expect(screen.getByRole("table", { name: "metrics" })).toHaveTextContent("30 / 30");   // server counts
    expect(screen.getByRole("table", { name: "per task" })).toHaveTextContent("shop-002differs");
  });

  it("shows a fair comparison as fair", async () => {
    fakeFetch({ [url]: { body: compareOut({ fair: true, unfair_dimensions: [], changed_dimensions: ["model"], tools_status: "same",
                                            conclusions: ["Changed dimension: model (the only configuration difference)."] }) } });
    open(url);
    expect(await screen.findByTestId("fairness")).toHaveTextContent("fair comparison");
    expect(screen.getByText("model", { selector: "strong" })).toBeInTheDocument();
  });

  it.each([
    [409, "incompatible_comparison", "runs of different suites cannot be compared: shop, shop-hard"],
    [422, "validation_error", "a comparison needs 2 to 5 suite ids (got 1)"],
  ])("shows the API's %s clearly", async (status, code, message) => {
    fakeFetch({ [url]: { status, body: { error: { code, message, details: null } } } });
    open(url);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(code);
    expect(alert).toHaveTextContent(message);
  });
});
