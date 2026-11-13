import { ConnectionPage } from "./pages/ConnectionPage";

// Step 10.1: one page. Routing (several pages) arrives in Step 10.2.
export function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-baseline gap-3 px-4 py-3">
          <h1 className="text-xl font-bold">AgentBench-Lite</h1>
          <span className="text-sm text-slate-500">AI agent evaluation &amp; reliability - local dashboard</span>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <ConnectionPage />
      </main>
    </div>
  );
}
