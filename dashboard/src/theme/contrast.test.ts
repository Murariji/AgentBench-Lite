// R1: WCAG contrast, computed from the REAL token values in src/index.css, for BOTH themes.
// A future colour change that makes text hard to read fails this test (and the build check).
import { describe, expect, it } from "vitest";
import css from "../index.css?raw";              // the file's exact text (Vite ?raw import)

function tokens(theme: "light" | "dark"): Record<string, [number, number, number]> {
  const block = css.match(new RegExp(`\\[data-theme="${theme}"\\]\\s*\\{([^}]*)\\}`))![1]!;
  const out: Record<string, [number, number, number]> = {};
  for (const m of block.matchAll(/--([\w-]+):\s*(\d+)\s+(\d+)\s+(\d+);/g)) out[m[1]!] = [Number(m[2]), Number(m[3]), Number(m[4])];
  return out;
}

/** WCAG 2.x relative luminance and contrast ratio. */
const luminance = (rgb: [number, number, number]) => {
  const [r, g, b] = rgb.map((v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
};
export const contrast = (a: [number, number, number], b: [number, number, number]) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
};

// [text, background]: every pair the components actually use for text.
const TEXT_PAIRS: [string, string][] = [
  ["fg", "bg"], ["fg", "surface"], ["fg", "surface-2"], ["fg", "accent-soft"],
  ["muted", "bg"], ["muted", "surface"], ["muted", "surface-2"],
  ["accent", "bg"], ["accent", "surface"], ["accent", "surface-2"],
  ["on-accent", "accent"], ["on-danger", "danger-solid"], ["danger-fg", "surface"],
  ["success-fg", "success-bg"], ["warning-fg", "warning-bg"], ["danger-fg", "danger-bg"],
  ["info-fg", "info-bg"], ["neutral-fg", "neutral-bg"],
];
// Non-text: the keyboard focus ring must be visible against what it surrounds (WCAG 1.4.11: 3:1).
const FOCUS_PAIRS: [string, string][] = [["accent", "bg"], ["accent", "surface"]];

describe.each(["light", "dark"] as const)("%s theme", (theme) => {
  const t = tokens(theme);

  it("defines exactly the same tokens as the other theme", () => {
    const other = tokens(theme === "light" ? "dark" : "light");
    expect(Object.keys(t).sort()).toEqual(Object.keys(other).sort());
  });

  it.each(TEXT_PAIRS)("text %s on %s reaches 4.5:1 (WCAG AA)", (fg, bg) => {
    expect(t[fg], `missing --${fg}`).toBeDefined();
    expect(t[bg], `missing --${bg}`).toBeDefined();
    expect(contrast(t[fg]!, t[bg]!)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(FOCUS_PAIRS)("focus ring %s around %s reaches 3:1", (ring, bg) => {
    expect(contrast(t[ring]!, t[bg]!)).toBeGreaterThanOrEqual(3);
  });
});

describe("the contrast formula itself", () => {
  it("matches known WCAG values", () => {
    expect(contrast([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 5);
    expect(contrast([118, 118, 118], [255, 255, 255])).toBeCloseTo(4.54, 2);   // the classic #767676 on white
  });
});
