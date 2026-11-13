// The application shell: a persistent sidebar (every section one click away), a top bar with the page
// title, the API connection indicator and the theme switcher, and a full-width content area.
// On small screens the sidebar becomes a menu opened from the top bar.
import { ArrowLeftRight, LayoutDashboard, List, Menu, Play, Plug, X, type LucideIcon } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { api, type Health } from "../api/client";
import { ThemeSwitcher } from "../theme/ThemeSwitcher";
import { Skeleton, StatusDot } from "./feedback";

type NavItem = { to: string; label: string; Icon: LucideIcon; active: (path: string) => boolean };

const NAV: NavItem[] = [
  { to: "/", label: "Overview", Icon: LayoutDashboard, active: (p) => p === "/" },
  { to: "/runs", label: "Runs", Icon: List, active: (p) => p === "/runs" || p.startsWith("/suites") || p.startsWith("/tasks") },
  { to: "/compare", label: "Compare", Icon: ArrowLeftRight, active: (p) => p.startsWith("/compare") },
  { to: "/runs/new", label: "Start a run", Icon: Play, active: (p) => p === "/runs/new" || p.startsWith("/jobs") },
  { to: "/connection", label: "API connection", Icon: Plug, active: (p) => p === "/connection" },
];

/** The page name shown in the top bar, from the address. */
export function pageTitle(path: string): string {
  if (path === "/") return "Overview";
  if (path === "/runs") return "Runs";
  if (path === "/runs/new") return "Start a run";
  if (path.startsWith("/jobs/")) return "Run progress";
  if (path.startsWith("/compare")) return "Compare";
  if (path === "/connection") return "API connection";
  if (/^\/suites\/[^/]+\/runs\//.test(path)) return "Trace";
  if (/^\/suites\/[^/]+\/failures/.test(path)) return "Failure analysis";
  if (path.startsWith("/suites/")) return "Run details";
  if (path.startsWith("/tasks/")) return "Task history";
  if (path === "/design") return "Design system";
  return "Not found";
}

const HEALTH_EVERY_MS = 30_000;

/** GET /health now and every 30 s: "connected", "unreachable" or "checking" - never guessed. */
function useHealth() {
  const [state, setState] = useState<{ status: "checking" } | { status: "ok"; health: Health } | { status: "down"; code: string }>(
    { status: "checking" });
  useEffect(() => {
    let active = true;
    const check = () => api.health()
      .then((health) => active && setState({ status: "ok", health }))
      .catch((e: { code?: string }) => active && setState({ status: "down", code: e?.code ?? "network_error" }));
    void check();
    const timer = setInterval(check, HEALTH_EVERY_MS);
    return () => { active = false; clearInterval(timer); };
  }, []);
  return state;
}

function ServerBox({ health }: { health: ReturnType<typeof useHealth> }) {
  return (
    <div className="mt-auto flex flex-col gap-2 rounded-lg border border-border bg-surface-2 p-3" aria-label="server status" role="group">
      <span className="text-xs font-semibold uppercase tracking-wider text-muted">Server</span>
      {health.status === "checking" && <StatusDot tone="off">checking…</StatusDot>}
      {health.status === "down" && <StatusDot tone="error">API unreachable ({health.code})</StatusDot>}
      {health.status === "ok" && (
        <>
          <StatusDot tone="ok">API connected</StatusDot>
          {health.health.real_runs_enabled
            ? <StatusDot tone="warn">Real Gemini runs ENABLED</StatusDot>
            : <StatusDot tone="off">Real runs disabled</StatusDot>}
        </>
      )}
    </div>
  );
}

export function AppShell() {
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const health = useHealth();
  const title = pageTitle(pathname);

  useEffect(() => setMenuOpen(false), [pathname]);                       // a link was followed: close the menu
  useEffect(() => { document.title = `${title} · AgentBench-Lite`; }, [title]);

  return (
    <div className="min-h-screen bg-bg text-body text-fg lg:flex">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>

      {menuOpen && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" aria-hidden="true" onClick={() => setMenuOpen(false)} />}
      <aside
        id="sidebar"
        className={`${menuOpen ? "fixed inset-y-0 left-0 z-40 flex" : "hidden"} w-64 flex-none flex-col gap-6 border-r border-border bg-surface px-3 py-4
          lg:sticky lg:top-0 lg:z-auto lg:flex lg:h-screen`}
      >
        <div className="flex items-center gap-2.5 px-2">
          <div aria-hidden="true" className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-xs font-bold text-on-accent">AB</div>
          <Link to="/" className="flex flex-col leading-tight">
            <span className="text-[15px] font-bold">AgentBench-Lite</span>
            <span className="text-xs text-muted">agent evaluation</span>
          </Link>
          <button type="button" className="ml-auto rounded-md p-1.5 text-muted hover:bg-surface-2 lg:hidden"
                  aria-label="Close menu" onClick={() => setMenuOpen(false)}>
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <nav aria-label="main" className="flex flex-col gap-0.5">
          {NAV.map(({ to, label, Icon, active }) => {
            const on = active(pathname);
            return (
              <Link key={to} to={to} aria-current={on ? "page" : undefined}
                    className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors ${
                      on ? "bg-accent-soft font-semibold text-fg" : "text-muted hover:bg-surface-2 hover:text-fg"}`}>
                <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                {label}
              </Link>
            );
          })}
        </nav>
        <ServerBox health={health} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex min-h-[60px] flex-wrap items-center gap-3 border-b border-border bg-bg/90 px-4 py-2 backdrop-blur sm:px-8">
          <button type="button" className="rounded-md p-1.5 text-muted hover:bg-surface-2 lg:hidden" aria-label="Open menu"
                  aria-expanded={menuOpen} aria-controls="sidebar" onClick={() => setMenuOpen(true)}>
            <Menu size={20} aria-hidden="true" />
          </button>
          <p className="flex items-center gap-2 text-sm">
            <span className="hidden text-muted sm:inline">AgentBench-Lite</span>
            <span className="hidden text-muted sm:inline" aria-hidden="true">/</span>
            <span className="font-semibold" data-testid="page-title">{title}</span>
          </p>
          <div className="ml-auto flex flex-wrap items-center gap-3">
            <span className="hidden items-center rounded-full border border-border bg-surface px-3 py-1 sm:inline-flex">
              {health.status === "ok" ? <StatusDot tone="ok">API connected</StatusDot>
                : health.status === "down" ? <StatusDot tone="error">API unreachable</StatusDot>
                : <StatusDot tone="off">checking API…</StatusDot>}
            </span>
            <ThemeSwitcher />
          </div>
        </header>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 focus:outline-none sm:px-8 sm:py-8">
          <Suspense fallback={<Skeleton lines={6} label="Loading page…" />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
