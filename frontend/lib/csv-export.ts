/**
 * A small, dependency-free CSV export utility (Phase 11, Step 15).
 *
 * A full-repo audit before this phase found NO CSV/PDF library or
 * download utility anywhere in this project (no `papaparse`, no
 * `jspdf`, no server-side `StreamingResponse`/`Content-Disposition`
 * pattern in the backend). CSV is simple, deterministic, and needs
 * nothing beyond string-joining + the browser's own download mechanism
 * -- introducing a dependency for it would violate the phase's own
 * "do not add a dependency merely because it makes this easier" rule.
 * PDF is deliberately NOT implemented here for the same reason; a
 * formatted copy is available via the browser's own Print (see
 * ReportsView's "Print" action, which just calls window.print()).
 */

function csvEscape(value: unknown): string {
  if (value == null) return "";
  const str = Array.isArray(value) ? value.join("; ") : String(value);
  if (/[",\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/** Builds a CSV string from an array of plain objects, using `columns`
 * to control column order/headers (object key order in JS is otherwise
 * unreliable across rows with optional fields). */
export function toCsv<T extends object>(rows: T[], columns: { key: keyof T; header: string }[]): string {
  const header = columns.map((c) => csvEscape(c.header)).join(",");
  const lines = rows.map((row) => columns.map((c) => csvEscape(row[c.key])).join(","));
  return [header, ...lines].join("\r\n");
}

/** Triggers a browser download of `content` as a file named `filename`.
 * Plain Blob + object URL -- the standard client-side download pattern,
 * no dependency. */
export function downloadCsv(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
