import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fakeFetch } from "../test/fakeApi";
import { ConnectionPage } from "./ConnectionPage";

const HEALTH = { status: "ok", schema_version: 3, real_runs_enabled: false };

describe("ConnectionPage", () => {
  it("shows 'Connecting…' first, then what the API reports", async () => {
    fakeFetch({ "/health": { body: HEALTH } });
    render(<ConnectionPage />);
    expect(screen.getByRole("status")).toHaveTextContent("Connecting");
    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("version 3")).toBeInTheDocument();
    expect(screen.getByText("disabled (scripted runs only)")).toBeInTheDocument();
  });

  it("says so clearly when real runs are enabled on the server", async () => {
    fakeFetch({ "/health": { body: { ...HEALTH, real_runs_enabled: true } } });
    render(<ConnectionPage />);
    expect(await screen.findByText("ENABLED on this server")).toBeInTheDocument();
  });

  it("explains an unreachable API and can try again", async () => {
    const { calls } = fakeFetch({ "/health": "network-down" });
    render(<ConnectionPage />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Not connected (network_error)");
    expect(alert).toHaveTextContent("python scripts/serve_api.py");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("alert");
    expect(calls).toEqual(["/health", "/health"]);
  });

  it("shows the API's own error code and message", async () => {
    fakeFetch({
      "/health": { status: 503, body: { error: { code: "storage_unavailable", message: "results database is broken", details: null } } },
    });
    render(<ConnectionPage />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("storage_unavailable");
    expect(alert).toHaveTextContent("results database is broken");
  });
});
