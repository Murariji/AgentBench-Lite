// Shares the theme with every component below it (React "context"): read it with useTheme().
// The FIRST paint is already correct (index.html's no-flash script); this provider keeps it correct
// afterwards: when the user switches, when the OS switches (System mode) and when another tab switches.
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState } from "react";
import {
  THEME_STORAGE_KEY, applyTheme, darkQuery, isPreference, readPreference, resolveTheme, savePreference,
  type ResolvedTheme, type ThemePreference,
} from "./theme";

type ThemeContextValue = {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setPreference: (preference: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(readPreference);
  const [systemDark, setSystemDark] = useState<boolean>(() => darkQuery()?.matches ?? false);

  useEffect(() => {
    // System mode follows the operating system LIVE (e.g. Windows switches to dark in the evening).
    const query = darkQuery();
    if (!query) return;
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    // Another tab of the dashboard changed the theme: follow it.
    const onStorage = (event: StorageEvent) => {
      if (event.key === THEME_STORAGE_KEY) setPreferenceState(isPreference(event.newValue) ? event.newValue : "system");
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const resolved = resolveTheme(preference, systemDark);
  useLayoutEffect(() => applyTheme(resolved), [resolved]);   // before the browser paints: no flicker

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    savePreference(next);
  }, []);

  const value = useMemo(() => ({ preference, resolved, setPreference }), [preference, resolved, setPreference]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme() must be used inside <ThemeProvider>");
  return value;
}
