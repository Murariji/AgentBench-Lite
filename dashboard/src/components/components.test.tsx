// R1: the reusable base components and the dev-only design page.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { DESIGN_PAGE_MARKER } from "../design/DesignPage";
import { Button } from "./Button";
import { MetricCard } from "./Card";
import { Alert, EmptyState, ErrorState, ProgressBar } from "./feedback";
import { Field, Input } from "./form";
import { DataTable } from "./Table";
import { CompleteBadge, KindBadge, ScopeBadge } from "./ui";

describe("MetricCard", () => {
  it("shows a real zero as 0, and a missing value as 'Not available' with the reason - never as 0", () => {
    render(<>
      <MetricCard label="Infra errors" value={0} />
      <MetricCard label="Active run" value={null} unavailableReason="The API could not be reached." />
    </>);
    expect(within(screen.getByRole("region", { name: "Infra errors" })).getByTestId("metric-value")).toHaveTextContent(/^0$/);
    const missing = screen.getByRole("region", { name: "Active run" });
    expect(within(missing).getByTestId("metric-unavailable")).toHaveTextContent("Not available");
    expect(missing).toHaveTextContent("The API could not be reached.");
    expect(missing).not.toHaveTextContent(/\b0\b/);
  });
});

describe("Field", () => {
  it("connects the label, the hint and the error to the control", () => {
    render(<Field label="Budget" hint="the hard cap" error="a real run needs a budget"><Input /></Field>);
    const input = screen.getByLabelText("Budget");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("the hard cap a real run needs a budget");
  });

  it("is not marked invalid without an error", () => {
    render(<Field label="Suite"><Input /></Field>);
    expect(screen.getByLabelText("Suite")).not.toHaveAttribute("aria-invalid");
  });
});

describe("Button", () => {
  it("is a real button (never submits a form by accident) and cannot be clicked when disabled", async () => {
    const onClick = vi.fn();
    render(<Button variant="primary" disabled onClick={onClick}>Start REAL run</Button>);
    const button = screen.getByRole("button", { name: "Start REAL run" });
    expect(button).toHaveAttribute("type", "button");
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("feedback states", () => {
  it("announces errors with the server's code and lets the user try again", async () => {
    const retry = vi.fn();
    render(<ErrorState title="Could not load" code="network_error" message="Cannot reach the API." onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load (network_error)");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("uses role=alert only for danger, and shows empty states and the server's progress", () => {
    render(<>
      <Alert tone="warning" title="Subset">not a full-suite score</Alert>
      <EmptyState title="No comparable full-suite runs yet" />
      <ProgressBar percent={22.2} label="job progress" />
    </>);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("No comparable full-suite runs yet")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "job progress" })).toHaveAttribute("aria-valuenow", "22.2");
  });
});

describe("honesty badges keep their exact labels after the restyle", () => {
  it("real vs scripted, subset, registration and incomplete", () => {
    render(<>
      <KindBadge kind="real" /><KindBadge kind="scripted" />
      <ScopeBadge scope="subset" registration="subset" /><ScopeBadge scope="unknown" registration="differs" />
      <CompleteBadge complete={false} />
    </>);
    for (const text of ["REAL LLM", "SCRIPTED", "SUBSET", "registered ✓", "task set unknown", "DIFFERS from registration", "INCOMPLETE"]) {
      expect(screen.getByText(text)).toBeInTheDocument();
    }
    expect(screen.getByText("SCRIPTED")).toHaveAttribute("title", "Fixed answers written in advance - not AI");
  });
});

describe("DataTable", () => {
  it("is labelled, has column headers and says so when empty", () => {
    const columns = [{ key: "id", header: "Run", cell: (r: { id: string }) => r.id }];
    const { rerender } = render(<DataTable label="runs" columns={columns} rows={[{ id: "b36e1e4a" }]} rowKey={(r) => r.id} />);
    const table = screen.getByRole("table", { name: "runs" });
    expect(within(table).getByRole("columnheader", { name: "Run" })).toBeInTheDocument();
    expect(within(table).getByRole("cell", { name: "b36e1e4a" })).toBeInTheDocument();
    rerender(<DataTable label="runs" columns={columns} rows={[]} rowKey={(r) => r.id} empty="No runs stored yet." />);
    expect(screen.getByText("No runs stored yet.")).toBeInTheDocument();
  });
});

describe("/design (development only)", () => {
  it("shows every component with a theme switcher, and both themes side by side on request", async () => {
    render(<MemoryRouter initialEntries={["/design"]}><AppRoutes /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: DESIGN_PAGE_MARKER })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Theme" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Show both themes side by side" }));
    expect(screen.getByRole("region", { name: "light theme" })).toHaveAttribute("data-theme", "light");
    expect(screen.getByRole("region", { name: "dark theme" })).toHaveAttribute("data-theme", "dark");
  });
});
