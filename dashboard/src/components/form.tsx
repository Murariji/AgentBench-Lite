// Form controls. <Field> connects a visible label, a hint and an error to its control (for screen readers:
// htmlFor/id, aria-describedby, aria-invalid), so every input is announced with its label and its problem.
import { cloneElement, forwardRef, isValidElement, useId } from "react";

const control =
  "w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm text-fg placeholder:text-muted " +
  "disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-danger-fg";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className = "", ...rest }, ref,
) {
  return <input ref={ref} className={`${control} ${className}`} {...rest} />;
});

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className = "", ...rest }, ref,
) {
  return <select ref={ref} className={`${control} ${className}`} {...rest} />;
});

export function Checkbox({ label, className = "", ...rest }: React.InputHTMLAttributes<HTMLInputElement> & { label: React.ReactNode }) {
  return (
    <label className={`inline-flex cursor-pointer items-center gap-2 text-sm text-fg ${className}`}>
      <input type="checkbox" className="h-4 w-4 rounded border-border-strong accent-[rgb(var(--accent))]" {...rest} />
      {label}
    </label>
  );
}

type FieldProps = { label: React.ReactNode; hint?: React.ReactNode; error?: React.ReactNode; children: React.ReactElement };

/** Wraps ONE control (Input, Select, ...) and wires its label, hint and error to it. */
export function Field({ label, hint, error, children }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  const child = isValidElement<Record<string, unknown>>(children)
    ? cloneElement(children, { id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })
    : children;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-medium text-fg">{label}</label>
      {child}
      {hint && <p id={hintId} className="text-xs text-muted">{hint}</p>}
      {error && <p id={errorId} className="text-xs font-medium text-danger-fg">{error}</p>}
    </div>
  );
}
