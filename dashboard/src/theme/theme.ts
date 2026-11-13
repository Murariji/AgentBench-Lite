// Theme logic as small PURE functions (easy to test). The no-flash script in index.html repeats the same
// few rules in plain JavaScript (it must run before React loads); theme.test.tsx proves the two agree.
//
//   preference = what the user chose:   "light" | "dark" | "system"
//   resolved   = what is actually drawn: "light" | "dark"   ("system" follows the operating system)

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "agentbench-theme";
export const THEME_PREFERENCES: readonly ThemePreference[] = ["light", "system", "dark"];
export const DARK_QUERY = "(prefers-color-scheme: dark)";

export function isPreference(value: unknown): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

/** The saved choice, or "system" when nothing (valid) is saved or storage is blocked. Never throws. */
export function readPreference(): ThemePreference {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isPreference(value) ? value : "system";
  } catch {
    return "system";
  }
}

/** Remember the choice across refreshes. Returns false (and keeps working) if storage is blocked. */
export function savePreference(preference: ThemePreference): boolean {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
    return true;
  } catch {
    return false;
  }
}

/** The operating system's colour-scheme query, or null where the browser has none (e.g. tests). */
export function darkQuery(): MediaQueryList | null {
  return typeof window.matchMedia === "function" ? window.matchMedia(DARK_QUERY) : null;
}

export function resolveTheme(preference: ThemePreference, systemDark: boolean): ResolvedTheme {
  if (preference === "system") return systemDark ? "dark" : "light";
  return preference;
}

/** Switch every token at once: the CSS variables in index.css follow `data-theme` on <html>. */
export function applyTheme(resolved: ResolvedTheme, root: HTMLElement = document.documentElement): void {
  root.setAttribute("data-theme", resolved);
  root.style.colorScheme = resolved;
}
