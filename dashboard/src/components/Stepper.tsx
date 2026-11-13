// "Where am I in this workflow?" - numbered steps; the current one is announced (aria-current="step").
import { Check } from "lucide-react";

export const RUN_STEPS = ["Configure", "Estimate", "Confirm & start", "Running", "Results"];

export function Stepper({ steps = RUN_STEPS, current }: { steps?: string[]; current: number }) {
  return (
    <ol aria-label="steps" className="flex flex-wrap items-center gap-x-2 gap-y-2 text-sm">
      {steps.map((label, i) => {
        const state = i < current ? "done" : i === current ? "current" : "todo";
        return (
          <li key={label} aria-current={state === "current" ? "step" : undefined} className="flex items-center gap-2">
            <span className={`grid h-6 w-6 place-items-center rounded-full text-xs font-semibold ${
              state === "done" ? "bg-success-bg text-success-fg" : state === "current" ? "bg-accent text-on-accent" : "bg-surface-2 text-muted"}`}>
              {state === "done" ? <Check size={14} aria-hidden="true" /> : i + 1}
            </span>
            <span className={state === "current" ? "font-semibold text-fg" : "text-muted"}>{label}</span>
            {i < steps.length - 1 && <span aria-hidden="true" className="mx-1 h-px w-6 bg-border-strong" />}
          </li>
        );
      })}
    </ol>
  );
}
