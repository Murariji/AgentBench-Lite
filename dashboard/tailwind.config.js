/** Tailwind scans these files for class names and generates only the CSS that is actually used.
 *  R1: theme colours are DESIGN TOKENS (CSS variables in src/index.css), so `bg-surface`, `text-fg`,
 *  `border-border`, `bg-success-bg text-success-fg`, ... follow the active theme (light or dark).
 *  The default Tailwind palette (slate, red, ...) is kept for the pages not yet migrated (R2-R5). */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;
const pair = (name) => ({ bg: token(`${name}-bg`), fg: token(`${name}-fg`) });

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        "surface-2": token("surface-2"),
        border: token("border"),
        "border-strong": token("border-strong"),
        fg: token("fg"),
        muted: token("muted"),
        accent: token("accent"),
        "on-accent": token("on-accent"),
        "accent-soft": token("accent-soft"),
        success: pair("success"),
        warning: pair("warning"),
        danger: { ...pair("danger"), solid: token("danger-solid") },
        "on-danger": token("on-danger"),
        info: pair("info"),
        neutral: pair("neutral"),
        "ok-dot": token("ok-dot"),
        "off-dot": token("off-dot"),
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      fontSize: {
        // body 15 px, tables 14 px, page title 26 px, metric numbers 28 px (approved design)
        body: ["15px", { lineHeight: "1.5" }],
        table: ["14px", { lineHeight: "1.45" }],
        title: ["26px", { lineHeight: "1.2", letterSpacing: "-0.01em", fontWeight: "700" }],
        metric: ["28px", { lineHeight: "1.15", letterSpacing: "-0.02em", fontWeight: "700" }],
      },
      borderColor: { DEFAULT: token("border") },   // a plain `border` uses the theme's border colour
      boxShadow: { card: "var(--shadow-card)" },
      borderRadius: { card: "12px" },
    },
  },
  plugins: [],
};
