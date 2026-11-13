// R1: theme preference, System detection, persistence, switching and the no-flash script.
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { mockSystemTheme } from "../test/media";
import { THEME_STORAGE_KEY, readPreference, resolveTheme, savePreference, type ThemePreference } from "./theme";
import { ThemeProvider } from "./ThemeProvider";
import { ThemeSwitcher } from "./ThemeSwitcher";
import indexHtml from "../../index.html?raw";     // exactly what the browser loads first

const html = () => document.documentElement;
const renderSwitcher = () => render(<ThemeProvider><ThemeSwitcher /></ThemeProvider>);
const button = (name: string) => screen.getByRole("button", { name });

describe("theme rules (pure functions)", () => {
  it("resolves every preference against the operating system", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });

  it("falls back to System for a missing or invalid saved value", () => {
    expect(readPreference()).toBe("system");
    window.localStorage.setItem(THEME_STORAGE_KEY, "purple");
    expect(readPreference()).toBe("system");
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    expect(readPreference()).toBe("dark");
  });

  it("keeps working when the browser blocks storage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(readPreference()).toBe("system");
    expect(savePreference("dark")).toBe(false);
  });
});

describe("no-flash script in index.html", () => {
  const script = indexHtml.match(/<script id="theme-init">([\s\S]*?)<\/script>/)![1]!;
  const cases: [ThemePreference | null, boolean][] = [
    [null, false], [null, true], ["light", true], ["dark", false], ["system", true], ["system", false],
  ];

  it.each(cases)("saved %s with OS dark=%s gives the same theme as the app", (saved, osDark) => {
    mockSystemTheme(osDark);
    if (saved) window.localStorage.setItem(THEME_STORAGE_KEY, saved);
    new Function(script)();                                            // exactly what the browser runs first
    expect(html().getAttribute("data-theme")).toBe(resolveTheme(saved ?? "system", osDark));
    expect(html().style.colorScheme).toBe(html().getAttribute("data-theme"));
  });

  it("does not crash when storage is blocked or matchMedia is missing", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    new Function(script)();
    expect(html().getAttribute("data-theme")).toBe("light");
  });
});

describe("ThemeProvider + ThemeSwitcher", () => {
  it("System (the default) follows the operating system", () => {
    mockSystemTheme(true);
    renderSwitcher();
    expect(button("System")).toHaveAttribute("aria-pressed", "true");
    expect(html()).toHaveAttribute("data-theme", "dark");
  });

  it("follows the operating system LIVE while System is selected", () => {
    const os = mockSystemTheme(false);
    renderSwitcher();
    expect(html()).toHaveAttribute("data-theme", "light");
    act(() => os.set(true));
    expect(html()).toHaveAttribute("data-theme", "dark");
  });

  it("a manual choice wins over the operating system", async () => {
    const os = mockSystemTheme(true);
    renderSwitcher();
    await userEvent.click(button("Light"));
    expect(html()).toHaveAttribute("data-theme", "light");
    act(() => os.set(true));
    expect(html()).toHaveAttribute("data-theme", "light");
  });

  it("remembers the choice across a refresh", async () => {
    mockSystemTheme(false);
    const first = renderSwitcher();
    await userEvent.click(button("Dark"));
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    first.unmount();                                                   // "refresh": a brand-new app
    html().removeAttribute("data-theme");
    renderSwitcher();
    expect(button("Dark")).toHaveAttribute("aria-pressed", "true");
    expect(html()).toHaveAttribute("data-theme", "dark");
  });

  it("can be used with the keyboard only", async () => {
    mockSystemTheme(false);
    renderSwitcher();
    const user = userEvent.setup();
    await user.tab();
    expect(button("Light")).toHaveFocus();
    await user.tab();
    await user.tab();
    expect(button("Dark")).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(html()).toHaveAttribute("data-theme", "dark");
    expect(button("Dark")).toHaveAttribute("aria-pressed", "true");
  });

  it("stops listening to the operating system when it is removed", () => {
    const os = mockSystemTheme(false);
    const view = renderSwitcher();
    expect(os.listenerCount()).toBe(1);
    view.unmount();
    expect(os.listenerCount()).toBe(0);
  });

  it("works where the browser has no matchMedia at all (light)", () => {
    renderSwitcher();
    expect(html()).toHaveAttribute("data-theme", "light");
  });
});

describe("every page follows the theme", () => {
  it("has no light-only lock left: the shell and pages use the active theme", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));     // keep the page loading; no network
    render(<MemoryRouter initialEntries={["/connection"]}><AppRoutes /></MemoryRouter>);
    expect(html()).toHaveAttribute("data-theme", "dark");
    const nav = screen.getByRole("navigation", { name: "main" });
    expect(nav.closest('[data-theme="light"]')).toBeNull();
    expect(within(screen.getByRole("banner")).getByRole("group", { name: "Theme" })).toBeInTheDocument();  // switcher in the top bar
  });
});
