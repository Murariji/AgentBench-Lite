// A fake `fetch` for tests: answers like the real API, but nothing leaves the test. No server needed.
import { vi } from "vitest";

export type FakeReply = { status?: number; body?: unknown; raw?: string } | "network-down";

export function fakeFetch(replies: Record<string, FakeReply>) {
  const calls: string[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url = new URL(String(input));
    const key = url.pathname + url.search;
    calls.push(key);
    const reply = replies[key];
    if (reply === undefined) throw new Error(`fakeFetch: no reply set up for ${key}`);
    if (reply === "network-down") throw new TypeError("Failed to fetch");
    const text = reply.raw ?? JSON.stringify(reply.body ?? null);
    return new Response(text, { status: reply.status ?? 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}
