// Fails if src/api/schema.d.ts is not exactly what openapi.json generates today.
// (tests/test_dashboard_openapi.py checks the other half: openapi.json matches the backend.)
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const fresh = join(mkdtempSync(join(tmpdir(), "abl-types-")), "schema.d.ts");
execFileSync(process.execPath, ["node_modules/openapi-typescript/bin/cli.js", "openapi.json", "-o", fresh],
  { stdio: "ignore" });
const normalise = (text) => text.replace(/\r\n/g, "\n");
if (normalise(readFileSync(fresh, "utf8")) !== normalise(readFileSync("src/api/schema.d.ts", "utf8"))) {
  console.error("src/api/schema.d.ts is out of date: run  npm run gen:types  (after python scripts/export_openapi.py)");
  process.exit(1);
}
console.log("TypeScript API types are up to date with openapi.json.");
