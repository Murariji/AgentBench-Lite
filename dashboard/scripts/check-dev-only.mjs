// Runs after `vite build`: fails if development-only code (the /design page) reached the production bundle.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const MARKERS = ["Design system (development only)", "Show both themes side by side"];
const files = [];
const walk = (dir) => {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path);
    else if (/\.(js|html|css)$/.test(name)) files.push(path);
  }
};
walk("dist");
const leaks = files.filter((f) => MARKERS.some((m) => readFileSync(f, "utf8").includes(m)));
if (leaks.length) {
  console.error(`FAIL: development-only /design code found in the production build: ${leaks.join(", ")}`);
  process.exit(1);
}
console.log(`OK: /design is not in the production build (${files.length} files checked).`);
