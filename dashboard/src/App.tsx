import { Suspense, lazy } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ThemeProvider } from "./theme/ThemeProvider";

// Every page is loaded only when it is opened ("code splitting"): the first load is small, and the chart
// library (Recharts) is downloaded only by the pages that draw charts.
const page = <K extends string>(load: () => Promise<Record<K, React.ComponentType>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));

const OverviewPage = page(() => import("./pages/OverviewPage"), "OverviewPage");
const RunsPage = page(() => import("./pages/RunsPage"), "RunsPage");
const RunDetailsPage = page(() => import("./pages/RunDetailsPage"), "RunDetailsPage");
const TraceViewerPage = page(() => import("./pages/TraceViewerPage"), "TraceViewerPage");
const FailuresPage = page(() => import("./pages/FailuresPage"), "FailuresPage");
const TaskHistoryPage = page(() => import("./pages/TaskHistoryPage"), "TaskHistoryPage");
const ComparePage = page(() => import("./pages/ComparePage"), "ComparePage");
const StartRunPage = page(() => import("./pages/StartRunPage"), "StartRunPage");
const RunJobPage = page(() => import("./pages/RunJobPage"), "RunJobPage");
const ConnectionPage = page(() => import("./pages/ConnectionPage"), "ConnectionPage");

// DEVELOPMENT ONLY: in a production build import.meta.env.DEV is `false`, so this import is removed
// from the bundle entirely (scripts/check-dev-only.mjs verifies it after every build).
const DesignPage = import.meta.env.DEV
  ? lazy(() => import("./design/DesignPage").then((m) => ({ default: m.DesignPage })))
  : null;

function NotFound() {
  return (
    <p role="alert" className="rounded-lg border border-border bg-surface p-4">
      Page not found. <Link to="/runs" className="font-medium text-accent hover:underline">All runs</Link>
    </p>
  );
}

/** The pages, by URL. Kept separate from BrowserRouter so tests can render them in a MemoryRouter. */
export function AppRoutes() {
  return (
    <ThemeProvider>
      <Routes>
        {DesignPage && (
          <Route path="/design" element={<Suspense fallback={<p role="status">Loading…</p>}><DesignPage /></Suspense>} />
        )}
        <Route element={<AppShell />}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/runs/new" element={<StartRunPage />} />
          <Route path="/jobs/:jobId" element={<RunJobPage />} />
          <Route path="/suites/:suiteId" element={<RunDetailsPage />} />
          <Route path="/suites/:suiteId/runs/:runId" element={<TraceViewerPage />} />
          <Route path="/suites/:suiteId/failures" element={<FailuresPage />} />
          <Route path="/tasks/:taskId" element={<TaskHistoryPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/connection" element={<ConnectionPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </ThemeProvider>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
