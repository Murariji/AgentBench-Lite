/** Tailwind scans these files for class names and generates only the CSS that is actually used. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
