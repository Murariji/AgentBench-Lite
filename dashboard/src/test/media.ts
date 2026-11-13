// A fake operating-system colour setting for tests (jsdom has no window.matchMedia).
// `set(true)` behaves like the user switching Windows to dark mode: listeners are told immediately.
import { vi } from "vitest";

export function mockSystemTheme(dark: boolean) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  const query = {
    matches: dark,
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => listeners.add(listener),
    removeEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener),
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => true,
  };
  window.matchMedia = vi.fn(() => query as unknown as MediaQueryList);
  return {
    set(next: boolean) {
      query.matches = next;
      listeners.forEach((listener) => listener({ matches: next } as MediaQueryListEvent));
    },
    listenerCount: () => listeners.size,
  };
}
