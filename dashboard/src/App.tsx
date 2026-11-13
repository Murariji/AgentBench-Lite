import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import { ComparePage } from "./pages/ComparePage";
import { ConnectionPage } from "./pages/ConnectionPage";
import { FailuresPage } from "./pages/FailuresPage";
import { RunDetailsPage } from "./pages/RunDetailsPage";
import { RunsPage } from "./pages/RunsPage";
import { TaskHistoryPage } from "./pages/TaskHistoryPage";
import { TraceViewerPage } from "./pages/TraceViewerPage";

const nav = ({ isActive }: { isActive: boolean }) =>
  `rounded px-2 py-1 text-sm ${isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`;

/** The pages, by URL. Kept separate from BrowserRouter so tests can render them in a MemoryRouter. */
export function AppRoutes() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
          <Link to="/" className="text-xl font-bold">AgentBench-Lite</Link>
          <nav className="flex gap-1" aria-label="main">
            <NavLink to="/" end className={nav}>Runs</NavLink>
            <NavLink to="/connection" className={nav}>API connection</NavLink>
          </nav>
          <span className="ml-auto text-xs text-slate-500">local dashboard · displays the API, computes nothing</span>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<RunsPage />} />
          <Route path="/suites/:suiteId" element={<RunDetailsPage />} />
          <Route path="/suites/:suiteId/runs/:runId" element={<TraceViewerPage />} />
          <Route path="/suites/:suiteId/failures" element={<FailuresPage />} />
          <Route path="/tasks/:taskId" element={<TaskHistoryPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/connection" element={<ConnectionPage />} />
          <Route path="*" element={<p role="alert">Page not found. <Link to="/" className="text-sky-700 underline">All runs</Link></p>} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
