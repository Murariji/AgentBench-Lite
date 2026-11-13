// Runs before every test file: adds DOM matchers such as toBeInTheDocument().
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup, configure } from "@testing-library/react";

// Pages are loaded on demand (code splitting); the first load of a page in a test run can take a moment.
configure({ asyncUtilTimeout: 15000 });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals(); // every test sets up its own fake fetch; nothing leaks between tests
  vi.restoreAllMocks();
  // R1 theme: no saved choice, no fake OS setting and no theme on <html> carries over to the next test.
  window.localStorage.clear();
  delete (window as { matchMedia?: unknown }).matchMedia;
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.style.colorScheme = "";
});
