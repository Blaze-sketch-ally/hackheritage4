import type { TrendAnalytics } from "@/types/institution-analytics-report";

function monthLabel(period: string): string {
  const [y, m] = period.split("-").map(Number);
  if (!y || !m) return period;
  return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: "short" });
}

/**
 * Monthly trend (Phase 6, Part 19) -- three series (applications /
 * selections / internship applications) bucketed by
 * applications.applied_at, the only reliable timestamp for this data
 * (see `trends.historical_note`, always rendered here). Pure CSS bars,
 * same visual language as components/industry/analytics/activity-timeline.tsx
 * -- no charting library, matching this project's existing convention.
 */
export function AnalyticsTrendChart({ trends }: { trends: TrendAnalytics }) {
  if (!trends.has_sufficient_data || trends.months.length === 0) {
    return <p className="text-sm text-muted-foreground/70">Not enough historical data yet.</p>;
  }

  const max = Math.max(1, ...trends.months.flatMap((p) => [p.applications, p.selections, p.internship_applications]));

  return (
    <div className="space-y-3">
      <div className="flex items-end gap-3">
        {trends.months.map((p) => (
          <div key={p.period} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex h-28 w-full items-end justify-center gap-1" aria-hidden="true">
              <span
                className="w-2.5 rounded-t bg-indigo-500/70"
                style={{ height: `${Math.round((p.applications / max) * 100)}%` }}
                title={`${p.applications} applications`}
              />
              <span
                className="w-2.5 rounded-t bg-emerald-500/70"
                style={{ height: `${Math.round((p.selections / max) * 100)}%` }}
                title={`${p.selections} selections`}
              />
              <span
                className="w-2.5 rounded-t bg-sky-500/70"
                style={{ height: `${Math.round((p.internship_applications / max) * 100)}%` }}
                title={`${p.internship_applications} internship applications`}
              />
            </div>
            <span className="text-[11px] text-muted-foreground">{monthLabel(p.period)}</span>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-indigo-500/70" aria-hidden="true" /> Applications
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-emerald-500/70" aria-hidden="true" /> Selections
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-sky-500/70" aria-hidden="true" /> Internship applications
        </span>
      </div>
      <table className="sr-only">
        <caption>Monthly application activity over the last 6 months</caption>
        <thead>
          <tr>
            <th>Month</th>
            <th>Applications</th>
            <th>Selections</th>
            <th>Internship applications</th>
          </tr>
        </thead>
        <tbody>
          {trends.months.map((p) => (
            <tr key={p.period}>
              <td>{p.period}</td>
              <td>{p.applications}</td>
              <td>{p.selections}</td>
              <td>{p.internship_applications}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
