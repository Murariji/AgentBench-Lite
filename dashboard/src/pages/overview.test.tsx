// The Overview page and the app shell (sidebar, top bar). Fake API only.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { RegisteredSuite } from "../api/client";
import { AppRoutes } from "../App";
import { pageTitle } from "../components/AppShell";
import { fakeFetch, type FakeReply } from "../test/fakeApi";
import { JOB_ID, jobOut, suitePage } from "../test/fixtures";
import { latestRealFullRun } from "./OverviewPage";

const CHART = "/suites?limit=100&offset=0";
const open = (path: string) => render(<MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>);
const total = (n: number) => ({ body: { items: [], pagination: { limit: 1, offset: 0, total: n, returned: 0, next_offset: null } } });
const REG: RegisteredSuite = {
  suite: "shop-hard", version: 1, registered_at: "2026-11-13T09:00:00Z", git_head: "cc973b7", suite_fingerprint: "5f106feaff34",
  tasks_fingerprint: "ca11f5077756", tools_fingerprint: "c1af5a87019e", tools: { sql_query: 1 }, dataset: null,
  tasks: ["hard-001", "hard-002", "hard-003", "hard-004", "hard-005", "hard-006", "hard-007", "hard-008", "hard-009"],
};
const jobsPage = (items: ReturnType<typeof jobOut>[]) =>
  ({ body: { items, pagination: { limit: 20, offset: 0, total: items.length, returned: items.length, next_offset: null } } });
const replies = (o: Record<string, FakeReply> = {}): Record<string, FakeReply> => ({
  "/health": { body: { status: "ok", schema_version: 3, real_runs_enabled: false } },
  "/suites?limit=1&offset=0": total(8), "/suites?limit=1&offset=0&real_only=true": total(6),
  "/registrations": { body: [REG] }, "/runs?limit=20&offset=0": jobsPage([]), [CHART]: { body: suitePage() }, ...o,
});
const card = (name: string) => screen.getByRole("region", { name });

describe("Overview", () => {
  it("shows the server's counts and the latest real full-suite run - nothing computed", async () => {
    fakeFetch(replies());
    open("/");
    expect(await within(await screen.findByRole("region", { name: "Stored runs" })).findByText("8")).toBeInTheDocument();
    expect(card("Stored runs")).toHaveTextContent("6 real-LLM run(s) · server counts");
    expect(await within(card("Registered suites")).findByText("1")).toBeInTheDocument();
    expect(card("Registered suites")).toHaveTextContent("shop-hard v1");
    const latest = card("Latest real full-suite run");
    expect(await within(latest).findByText("0af951e0")).toBeInTheDocument();     // newest REAL run with scope full
    expect(latest).toHaveTextContent("30/30");
    expect(latest).toHaveTextContent("(100.0%)");
    expect(await within(card("Active run")).findByText("None")).toBeInTheDocument();
  });

  it("lists registered and unregistered suites, and unknown tools honestly", async () => {
    fakeFetch(replies({ [CHART]: { body: { ...suitePage(), items: suitePage().items.map((s, i) => i === 2 ? { ...s, tools_fingerprint: null } : s) } } }));
    open("/");
    const suites = await screen.findByRole("list", { name: "suites" });
    expect(suites).toHaveTextContent("shop-hardregistered v1");
    expect(suites).toHaveTextContent("shopunregistered");
    expect(await within(suites).findByText(/Tools not recorded for 0af951e0/)).toBeInTheDocument();
  });

  it("says 'Not available' (never 0) when a value cannot be loaded", async () => {
    const broken = { status: 503, body: { error: { code: "storage_unavailable", message: "database broken", details: null } } };
    fakeFetch(replies({ "/registrations": broken }));
    open("/");
    const regs = await screen.findByRole("region", { name: "Registered suites" });
    expect(await within(regs).findByTestId("metric-unavailable")).toHaveTextContent("Not available");
    expect(regs).toHaveTextContent("Could not load (storage_unavailable).");
    expect(within(regs).queryByTestId("metric-value")).not.toBeInTheDocument();
  });

  it("links to a run in progress", async () => {
    fakeFetch(replies({ "/runs?limit=20&offset=0": jobsPage([jobOut()]) }));
    open("/");
    const active = await screen.findByRole("region", { name: "Active run" });
    expect(await within(active).findByRole("link", { name: /follow it/ })).toHaveAttribute("href", `/jobs/${JOB_ID}`);
    expect(active).toHaveTextContent("1/2");
  });

  it("picks the newest REAL full-suite run, never a subset or a scripted run", () => {
    const items = suitePage().items;                                 // [real subset, scripted unknown, real full, scripted full]
    expect(latestRealFullRun(items)?.short_id).toBe("0af951e0");
    expect(latestRealFullRun(items.filter((s) => s.short_id !== "0af951e0"))).toBeUndefined();
  });
});

describe("app shell", () => {
  it("has a sidebar link to every section, marks the current page and names it in the top bar", async () => {
    fakeFetch(replies());
    open("/runs");
    const nav = screen.getByRole("navigation", { name: "main" });
    const links = within(nav).getAllByRole("link").map((l) => [l.textContent, l.getAttribute("href")]);
    expect(links).toEqual([["Overview", "/"], ["Runs", "/runs"], ["Compare", "/compare"], ["Start a run", "/runs/new"], ["API connection", "/connection"]]);
    expect(within(nav).getByRole("link", { name: "Runs" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByTestId("page-title")).toHaveTextContent("Runs");
    fireEvent.click(within(nav).getByRole("link", { name: "Start a run" }));
    expect(within(nav).getByRole("link", { name: "Start a run" })).toHaveAttribute("aria-current", "page");
  });

  it("shows whether the API is reachable and whether real runs are on - from GET /health", async () => {
    fakeFetch(replies({ "/health": { body: { status: "ok", schema_version: 3, real_runs_enabled: true } } }));
    open("/connection");
    const server = screen.getByRole("group", { name: "server status" });
    expect(await within(server).findByText("API connected")).toBeInTheDocument();
    expect(server).toHaveTextContent("Real Gemini runs ENABLED");
  });

  it("says so when the API cannot be reached", async () => {
    fakeFetch({ "/health": "network-down" });
    open("/compare");
    expect(await within(screen.getByRole("group", { name: "server status" })).findByText(/API unreachable \(network_error\)/)).toBeInTheDocument();
  });

  it("opens the menu on small screens", () => {
    fakeFetch(replies());
    open("/compare");
    const button = screen.getByRole("button", { name: "Open menu" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: "Close menu" }));
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("names every page in the top bar", () => {
    expect(["/", "/runs", "/runs/new", "/jobs/abc", "/compare", "/suites/x", "/suites/x/runs/y", "/suites/x/failures", "/tasks/t", "/nope"].map(pageTitle))
      .toEqual(["Overview", "Runs", "Start a run", "Run progress", "Compare", "Run details", "Trace", "Failure analysis", "Task history", "Not found"]);
  });
});

describe("Compare from the sidebar", () => {
  it("explains how to choose runs instead of sending an empty request", async () => {
    const { calls } = fakeFetch(replies());
    open("/compare");
    expect(await screen.findByText("Choose 2 to 5 runs of one suite")).toBeInTheDocument();
    expect(calls.some((c) => c.startsWith("/compare"))).toBe(false);
  });
});
