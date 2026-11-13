// Light / System / Dark. Three real <button>s (reachable with Tab, pressed with Enter or Space);
// aria-pressed tells screen readers which one is active.
import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import type { ThemePreference } from "./theme";
import { useTheme } from "./ThemeProvider";

const OPTIONS: { value: ThemePreference; label: string; Icon: LucideIcon }[] = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "system", label: "System", Icon: Monitor },
  { value: "dark", label: "Dark", Icon: Moon },
];

export function ThemeSwitcher() {
  const { preference, resolved, setPreference } = useTheme();
  return (
    <div role="group" aria-label="Theme" className="inline-flex gap-0.5 rounded-lg border border-border bg-surface-2 p-[3px]">
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = preference === value;
        return (
          <button
            key={value}
            type="button"
            aria-pressed={active}
            title={value === "system" ? `Follow the operating system (now ${resolved})` : `${label} theme`}
            onClick={() => setPreference(value)}
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors ${
              active ? "bg-surface text-fg shadow-[0_0_0_1px_rgb(var(--border-strong))]" : "text-muted hover:text-fg"
            }`}
          >
            <Icon size={15} strokeWidth={1.8} aria-hidden="true" />
            {label}
          </button>
        );
      })}
    </div>
  );
}
