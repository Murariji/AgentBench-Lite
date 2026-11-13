// A readable data table: labelled for screen readers, header row on a tinted band, numbers right-aligned
// with equal-width digits, and horizontal scrolling inside its own box on narrow screens (never the page).

export type Column<T> = {
  key: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  align?: "left" | "right";
};

export function DataTable<T>({ label, columns, rows, rowKey, empty = "No rows." }: {
  label: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  empty?: React.ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table aria-label={label} className="w-full border-collapse text-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col"
                  className={`whitespace-nowrap border-y border-border bg-surface-2 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-muted ${c.align === "right" ? "text-right" : "text-left"}`}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td colSpan={columns.length} className="px-4 py-6 text-center text-muted">{empty}</td></tr>
          ) : rows.map((row) => (
            <tr key={rowKey(row)} className="hover:bg-surface-2/60">
              {columns.map((c) => (
                <td key={c.key} className={`border-b border-border px-4 py-3 align-middle ${c.align === "right" ? "text-right tabular-nums" : ""}`}>
                  {c.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
