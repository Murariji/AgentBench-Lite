// The width of an element, kept up to date when the window or the sidebar changes size.
// Charts use it to fill their card instead of a fixed width. Falls back to `fallback` where the browser
// has no ResizeObserver (tests).
import { useEffect, useRef, useState } from "react";

export function useWidth<T extends HTMLElement>(fallback = 760, min = 320) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const w = Math.floor(entry?.contentRect.width ?? 0);
      if (w > 0) setWidth(Math.max(min, w));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [min]);
  return [ref, width] as const;
}
