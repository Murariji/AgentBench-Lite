// The chart width follows its box - also when the box appears only AFTER loading (the bug this guards).
import { act, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { useWidth } from "./useWidth";

function Late() {
  const [ready, setReady] = useState(false);
  const [ref, width] = useWidth<HTMLDivElement>(760);
  return (
    <>
      <button onClick={() => setReady(true)}>load</button>
      {ready && <div ref={ref} data-testid="box">{width}</div>}
    </>
  );
}

describe("useWidth", () => {
  it("measures a box that appears after the first render", () => {
    let callback: ResizeObserverCallback = () => undefined;
    vi.stubGlobal("ResizeObserver", class {
      constructor(cb: ResizeObserverCallback) { callback = cb; }
      observe() {} disconnect() {} unobserve() {}
    });
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ width: 1100 } as DOMRect);
    render(<Late />);
    act(() => screen.getByRole("button", { name: "load" }).click());
    expect(screen.getByTestId("box")).toHaveTextContent("1100");                  // measured at once
    act(() => callback([{ contentRect: { width: 900 } } as ResizeObserverEntry], {} as ResizeObserver));
    expect(screen.getByTestId("box")).toHaveTextContent("900");                   // and on resize
  });
});
