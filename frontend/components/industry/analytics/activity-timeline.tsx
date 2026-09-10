import type { TimePoint } from "@/types/analytics";

function monthLabel(period: string): string {
  const [y, m] = period.split("-").map(Number);
  if (!y || !m) return period;
  return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: "short" });
}

/** Two-series monthly bars (postings created / applications received)
 * over the last 6 months. Creation-date facts only — never inferred
 * status history. Pure CSS, no charting library. */
export function ActivityTimeline({ timeline }: { timeline: TimePoint[] }) {
  const max = Math.max(
    1,
    ...timeline.flatMap((p) => [p.opportunities_created, p.applications_received]),
  );
  const allZero = timeline.every(
    (p) => p.opportunities_created === 0 && p.applications_received === 0,
  );

  if (allZero) {
    return (
      <p className="text-sm text-muted-foreground/70">
        Nothing created or received in the last 6 months.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-end gap-3">
        {timeline.map((p) => (
          <div key={p.period} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex h-28 w-full items-end justify-center gap-1" aria-hidden="true">
              <span
                className="w-3 rounded-t bg-indigo-500/70"
                style={{ height: `${Math.round((p.opportunities_created / max) * 100)}%` }}
                title={`${p.opportunities_created} postings created`}
              />
              <span
                className="w-3 rounded-t bg-sky-500/70"
                style={{ height: `${Math.round((p.applications_received / max) * 100)}%` }}
                title={`${p.applications_received} applications received`}
              />
            </div>
            <span className="text-[11px] text-muted-foreground">{monthLabel(p.period)}</span>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-indigo-500/70" aria-hidden="true" /> Postings created
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-sky-500/70" aria-hidden="true" /> Applications received
        </span>
      </div>
      <table className="sr-only">
        <caption>Monthly activity over the last 6 months</caption>
        <thead>
          <tr>
            <th>Month</th>
            <th>Postings created</th>
            <th>Applications received</th>
          </tr>
        </thead>
        <tbody>
          {timeline.map((p) => (
            <tr key={p.period}>
              <td>{p.period}</td>
              <td>{p.opportunities_created}</td>
              <td>{p.applications_received}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
