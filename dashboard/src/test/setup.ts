// Runs before every test file: adds DOM matchers such as toBeInTheDocument().
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals(); // every test sets up its own fake fetch; nothing leaks between tests
});
