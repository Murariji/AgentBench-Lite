// The pass-rate-over-time rules, tested on the pure reshaping functions (no rendering, no network).
import { describe, expect, it } from "vitest";
import { summary } from "../test/fixtures";
import { buildTrend, groupKey, ineligibility } from "./trend";

const rate = (passed: number, eligible: number, text?: string) =>
  ({ passed, eligible, rate: eligible ? passed / eligible : null, text: text ?? `${passed}/${eligible}` });

// A "comparable" run: registered, full suite, complete - the only kind that may be on a line.
const ok = (id: string, day: number, o = {}) => summary({
  suite_id: `${id}${"0".repeat(32 - id.length)}`, short_id: id, started_at: `2026-11-${String(day).padStart(2, "0")}T10:00:00Z`,
  registration_status: "matches", scope: "full", complete: true, pass_rate: rate(7, 9), ...o,
});

describe("eligibility", () => {
  it("only matches + full + complete may be connected", () => {
    expect(ineligibility(ok("a", 1))).toEqual([]);
    expect(ineligibility(ok("a", 1, { scope: "subset", registration_status: "subset" }))).toContain("subset (not a full-suite score)");
    expect(ineligibility(ok("a", 1, { registration_status: "differs" }))).toContain("differs from registration");
    expect(ineligibility(ok("a", 1, { registration_status: "unregistered" }))).toEqual(["unregistered suite"]);
    expect(ineligibility(ok("a", 1, { complete: false }))).toEqual(["incomplete"]);
    expect(ineligibility(ok("a", 1, { scope: "unknown", registration_status: "unknown" }))).toContain("task set unknown");
  });
});

describe("grouping (six-part key)", () => {
  it("never merges different configs, tools, models or kinds", () => {
    const base = ok("a", 1);
    const keys = new Set([
      groupKey(base),
      groupKey(ok("b", 2, { config_fingerprint: "other0000000" })),
      groupKey(ok("c", 3, { tools_fingerprint: "other0000000" })),
      groupKey(ok("d", 4, { tools_fingerprint: null })),            // unknown tools: its own group
      groupKey(ok("e", 5, { model: "another-model" })),
      groupKey(ok("f", 6, { kind: "scripted", provider: "fake" })),
      groupKey(ok("g", 7, { suite_name: "shop" })),
    ]);
    expect(keys.size).toBe(7);
    expect(groupKey(ok("h", 8))).toBe(groupKey(base));             // same six parts: same group
  });

  it("unknown tools never equal a fingerprint that happens to be named 'unknown'", () => {
    expect(groupKey(ok("a", 1, { tools_fingerprint: null }))).not.toBe(groupKey(ok("b", 2, { tools_fingerprint: "unknown" })));
  });
});

describe("buildTrend", () => {
  it("sorts and connects each group on its own; other runs cannot interrupt it", () => {
    const items = [
      ok("a3", 3), ok("x2", 2, { config_fingerprint: "other0000000" }), ok("a1", 1),
      ok("s2", 2, { scope: "subset", registration_status: "subset" }),        // between a1 and a3 in time
    ];
    const t = buildTrend(items);
    expect(t.groups).toHaveLength(2);
    const main = t.groups.find((g) => g.points.length === 2)!;
    expect(main.points.map((p) => p.shortId)).toEqual(["a1", "a3"]);           // the subset is NOT in between
    expect(t.markers.map((m) => [m.shortId, m.marker])).toEqual([["s2", "subset"]]);
    expect(t.groups.find((g) => g.points.length === 1)!.baseline).toBe(true); // one run = a baseline
    expect(main.baseline).toBe(false);
  });

  it("plots the server's rate unchanged and keeps null as no point", () => {
    const t = buildTrend([ok("a", 1, { pass_rate: rate(2, 3, "2/3 (66.7%)") }),
                          ok("n", 2, { pass_rate: { passed: 0, eligible: 0, rate: null, text: "0/0 (n/a)" } })]);
    expect(t.groups[0]!.points[0]).toMatchObject({ rate: 2 / 3, rateText: "2/3 (66.7%)" });
    expect(t.noValue.map((s) => s.short_id)).toEqual(["n"]);
    expect([...t.groups.flatMap((g) => g.points), ...t.markers].some((p) => p.shortId === "n")).toBe(false);
  });

  it("marks every kind of non-comparable run, and keeps them off lines", () => {
    const t = buildTrend([
      ok("i", 1, { complete: false }), ok("d", 2, { registration_status: "differs" }),
      ok("s", 3, { scope: "subset", registration_status: "subset" }), ok("u", 4, { registration_status: "unregistered" }),
      ok("k", 5, { scope: "unknown", registration_status: "unknown", tasks_fingerprint: null }),
    ]);
    expect(t.groups).toEqual([]);
    expect(t.markers.map((m) => m.marker)).toEqual(["incomplete", "differs", "subset", "unregistered", "unknown"]);
  });

  it("hides scripted runs unless asked", () => {
    const items = [ok("r", 1), ok("f", 2, { kind: "scripted", provider: "fake" })];
    expect(buildTrend(items).hiddenScripted).toBe(1);
    expect(buildTrend(items, { includeScripted: true }).groups).toHaveLength(2);
  });
});
