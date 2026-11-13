// Starting a run (guided: configure -> estimate -> confirm & start) and following it live.
// Fake API only - nothing is ever sent to Gemini in tests.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../App";
import { fakeFetch, type FakeReply } from "../test/fakeApi";
import { JOB_ID, estimateOut, jobOut } from "../test/fixtures";
import { RunJobPage, clock } from "./RunJobPage";
import { toRequest } from "./StartRunPage";

const HEALTH = (enabled: boolean) => ({ status: "ok", schema_version: 3, real_runs_enabled: enabled });
const JOB = `/runs/${JOB_ID}`;
const open = (path: string) => render(<MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>);
const field = (label: RegExp) => screen.getByLabelText(label);
const estimateBtn = () => screen.getByRole("button", { name: "Estimate" });
const startBtn = () => screen.getByRole("button", { name: /^Start (REAL|scripted) run$/ });
const posted = (sent: { method: string; path: string; body: unknown }[], path: string) =>
  sent.filter((s) => s.method === "POST" && s.path === path).map((s) => s.body);
const openStart = async () => { open("/runs/new"); await screen.findByRole("button", { name: "Estimate" }); };

describe("the request the page sends", () => {
  it("sends exactly what the form says, and never confirms a scripted run", () => {
    const base = { suite: "shop-hard", tasks: "", repeats: "1", budget: "", confirm: true };
    expect(toRequest({ ...base, agent: "gemini", budget: "30" }))
      .toEqual({ agent: "gemini", suite: "shop-hard", repeats: 1, budget: 30, confirm: true });
    expect(toRequest({ ...base, agent: "careful", budget: "30", tasks: "hard-001, hard-007" }))
      .toEqual({ agent: "careful", suite: "shop-hard", repeats: 1, tasks: ["hard-001", "hard-007"], confirm: false });
    expect(toRequest({ ...base, agent: "gemini", confirm: false })).not.toHaveProperty("budget");   // no invented budget
  });
});

describe("Start a run (guided)", () => {
  it("explains how to enable real runs and shows the server's refusal when they are off", async () => {
    const refused = estimateOut({ real_runs_enabled: false, allowed: false, reasons: [
      "real Gemini runs are disabled on this server (start it with --allow-real-runs to enable them)",
      "a real run needs confirm=true"] });
    const { sent } = fakeFetch({ "/health": { body: HEALTH(false) }, "/estimates": { body: refused } });
    await openStart();
    expect(await screen.findByTestId("real-disabled")).toHaveTextContent("python scripts/serve_api.py --allow-real-runs");
    fireEvent.click(estimateBtn());
    const verdict = await screen.findByTestId("verdict");
    expect(verdict).toHaveTextContent("would NOT start");
    expect(verdict).toHaveTextContent("disabled on this server");
    expect(startBtn()).toBeDisabled();
    expect(posted(sent, "/estimates")).toEqual([{ agent: "gemini", suite: "shop-hard", repeats: 1, confirm: false }]);
    expect(posted(sent, "/runs")).toEqual([]);                                   // nothing was started
  });

  it("walks through estimate -> confirm (asks the server again) -> start, then follows the job", async () => {
    const { sent } = fakeFetch({ "/health": { body: HEALTH(true) }, "/estimates": { body: estimateOut() },
                                 "/runs": { status: 202, body: jobOut() }, [JOB]: { body: jobOut() } });
    await openStart();
    expect(await screen.findByText("REAL runs enabled")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "steps" })).getByText("Configure").closest("li")).toHaveAttribute("aria-current", "step");
    fireEvent.change(field(/^Budget/), { target: { value: "100" } });
    expect(field(/I confirm/)).toBeDisabled();                                    // estimate first
    fireEvent.click(estimateBtn());
    await screen.findByTestId("verdict");
    expect(screen.getByLabelText("estimate")).toHaveTextContent("typical 63, worst case 90");
    expect(screen.getByLabelText("estimate")).toHaveTextContent("matches shop-hard v1");
    fireEvent.click(field(/I confirm/));
    await waitFor(() => expect(posted(sent, "/estimates")).toHaveLength(2));       // the confirmed request, asked again
    await waitFor(() => expect(startBtn()).toBeEnabled());
    expect(startBtn()).toHaveTextContent("Start REAL run");
    fireEvent.click(startBtn());
    expect(await screen.findByRole("heading", { name: /Run job 1234abcd/ })).toBeInTheDocument();
    expect(posted(sent, "/estimates")).toEqual([
      { agent: "gemini", suite: "shop-hard", repeats: 1, budget: 100, confirm: false },
      { agent: "gemini", suite: "shop-hard", repeats: 1, budget: 100, confirm: true },
    ]);
    expect(posted(sent, "/runs")).toEqual([{ agent: "gemini", suite: "shop-hard", repeats: 1, budget: 100, confirm: true }]);
  });

  it("asks for a new estimate when the form changes after estimating", async () => {
    fakeFetch({ "/health": { body: HEALTH(true) }, "/estimates": { body: estimateOut({ agent: "careful", kind: "scripted", estimate: null }) } });
    await openStart();
    fireEvent.change(field(/^Agent/), { target: { value: "careful" } });
    fireEvent.click(estimateBtn());
    await screen.findByTestId("verdict");
    expect(startBtn()).toBeEnabled();
    fireEvent.change(field(/^Repeats/), { target: { value: "3" } });
    expect(screen.getByTestId("stale")).toHaveTextContent("estimate again");
    expect(startBtn()).toBeDisabled();
    expect(screen.queryByTestId("verdict")).not.toBeInTheDocument();          // the old estimate is not shown
  });

  it("runs a scripted agent without budget or confirmation, and warns about subsets", async () => {
    const { sent } = fakeFetch({ "/health": { body: HEALTH(false) },
      "/estimates": { body: estimateOut({ agent: "careful", kind: "scripted", estimate: null, tasks: ["hard-001"], runs: 1 }) } });
    await openStart();
    fireEvent.change(field(/^Agent/), { target: { value: "careful" } });
    expect(screen.queryByLabelText(/^Budget/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/I confirm/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("real-disabled")).not.toBeInTheDocument();
    fireEvent.change(field(/^Tasks/), { target: { value: "hard-001" } });
    expect(screen.getByText(/not a full-suite score/)).toBeInTheDocument();
    fireEvent.click(estimateBtn());
    expect(await screen.findByTestId("verdict")).toHaveTextContent("would accept");
    expect(screen.getByLabelText("estimate")).toHaveTextContent("SCRIPTED");
    expect(startBtn()).toHaveTextContent("Start scripted run");
    expect(posted(sent, "/estimates")).toEqual([{ agent: "careful", suite: "shop-hard", repeats: 1, tasks: ["hard-001"], confirm: false }]);
  });

  it("shows a run already in progress and links to it", async () => {
    fakeFetch({ "/health": { body: HEALTH(true) }, "/estimates": { body: estimateOut({ agent: "careful", kind: "scripted", estimate: null }) },
      "/runs": { status: 409, body: { error: { code: "run_in_progress", message: "a benchmark run is already in progress (job 1234abcd, status running)",
                                               details: { active_job_id: JOB_ID } } } } });
    await openStart();
    fireEvent.change(field(/^Agent/), { target: { value: "careful" } });
    fireEvent.click(estimateBtn());
    await screen.findByTestId("verdict");
    fireEvent.click(startBtn());
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("run_in_progress");
    expect(within(alert).getByRole("link", { name: "Follow the run in progress" })).toHaveAttribute("href", `/jobs/${JOB_ID}`);
  });
});

describe("following a run live", () => {
  const openJob = () => render(
    <MemoryRouter initialEntries={[`/jobs/${JOB_ID}`]}>
      <Routes><Route path="/jobs/:jobId" element={<RunJobPage pollMs={5} />} /></Routes>
    </MemoryRouter>);

  it("shows the task, the step, the requests against the budget and a moving clock; stops polling when done", async () => {
    const replies: Record<string, FakeReply> = { [JOB]: { body: jobOut() } };
    const { calls } = fakeFetch(replies);
    openJob();
    expect(await screen.findByTestId("now")).toHaveTextContent("Task 2 of 2: hard-002 · step 2 of max 10");
    expect(screen.getByTestId("requests")).toHaveTextContent("7 / 30 requests used (retries included)");
    expect(screen.getByTestId("counts")).toHaveTextContent("1 / 2 runs done");
    expect(screen.getByTestId("elapsed")).toHaveTextContent(/^Elapsed \d+:\d{2}/);
    expect(screen.getByRole("progressbar", { name: "progress" })).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("hard-002 · working…")).toBeInTheDocument();
    replies[JOB] = { body: jobOut({ status: "finished", percent: 100, completed_tasks: 2, current_task: null, current_repeat: null,
                                    current_step: null, total_steps: null, llm_calls_used: 12, finished_at: "2026-11-13T10:01:31Z",
                                    saved: true, suite_id: "9999aaaa9999aaaa9999aaaa9999aaaa",
                                    summary: { pass_rate: "2/2 (100.0%)", requests: 12 },
                                    progress: ["hard-001 #1: passed (5 requests)", "hard-002 #1: passed (7 requests)"] }) };
    const link = await screen.findByRole("link", { name: /Open the results \(9999aaaa\)/ });
    expect(link).toHaveAttribute("href", "/suites/9999aaaa9999aaaa9999aaaa9999aaaa");
    expect(screen.getByTestId("elapsed")).toHaveTextContent("Took 1:30");      // finished_at - started_at (server times)
    expect(screen.getByTestId("summary")).toHaveTextContent("2/2 (100.0%)");
    const count = calls.length;
    await new Promise((r) => setTimeout(r, 50));
    expect(calls.length).toBe(count);                                            // polling stopped
  });

  it("never invents a step when the server does not report one", async () => {
    fakeFetch({ [JOB]: { body: jobOut({ current_step: null, total_steps: null, kind: "scripted", budget: null }) } });
    openJob();
    expect(await screen.findByTestId("now")).not.toHaveTextContent("step");
    expect(screen.getByTestId("requests")).toHaveTextContent("7 scripted call(s) - nothing sent to any model");
  });

  it("is honest about an incomplete run that could not be saved", async () => {
    fakeFetch({ [JOB]: { body: jobOut({ status: "incomplete", saved: false, save_error: "database is locked",
                                       recovery_path: "results/recovery/1234abcd.json", current_task: null }) } });
    openJob();
    expect(await screen.findByText(/stopped early/i, { selector: "p" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("could NOT be saved");
    expect(screen.getByRole("alert")).toHaveTextContent("results/recovery/1234abcd.json");
    expect(screen.queryByRole("link", { name: /Open the results/ })).not.toBeInTheDocument();
  });

  it("explains a job the server no longer knows", async () => {
    fakeFetch({ [JOB]: { status: 404, body: { error: { code: "not_found", message: "no job ... Job status is kept in memory only", details: null } } } });
    openJob();
    expect(await screen.findByRole("alert")).toHaveTextContent("kept in memory only");
  });

  it("formats the clock", () => {
    expect([clock(0), clock(65_000), clock(3_725_000)]).toEqual(["0:00", "1:05", "1:02:05"]);
  });
});
