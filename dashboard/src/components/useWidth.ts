// The width of an element, kept up to date when the window or the sidebar changes size.
// Charts use it to fill their card instead of a fixed width. Falls back to `fallback` where the browser
// has no ResizeObserver (tests).
//
// A "callback ref" (a function React calls when the element appears or disappears) is used, NOT useRef +
// useEffect: a chart's box only appears AFTER its data has loaded, so an effect that runs once at the first
// render would find no element and never measure (the chart would stay at the fallback width).
import { useCallback, useEffect, useRef, useState } from "react";

export function useWidth<T extends HTMLElement>(fallback = 760, min = 320) {
  const [width, setWidth] = useState(fallback);
  const observer = useRef<ResizeObserver | null>(null);

  const ref = useCallback((el: T | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!el || typeof ResizeObserver === "undefined") return;
    const measure = (w: number) => { if (w > 0) setWidth(Math.max(min, Math.floor(w))); };
    measure(el.getBoundingClientRect().width);                 // at once, then on every resize
    observer.current = new ResizeObserver(([entry]) => measure(entry?.contentRect.width ?? 0));
    observer.current.observe(el);
  }, [min]);

  useEffect(() => () => observer.current?.disconnect(), []);
  return [ref, width] as const;
}
