import { cn } from "@/lib/utils";

export interface BarDatum {
  key: string;
  label: string;
  value: number;
  /** Optional secondary number shown after the label, e.g. "3 published". */
  hint?: string;
}

/** A deterministic horizontal bar list — count per row with a
 * proportional bar. Same visual language as the recruitment funnel; no
 * charting library. */
export function BarList({
  data,
  emptyText = "No data yet.",
  accentClass = "bg-indigo-500/70",
}: {
  data: BarDatum[];
  emptyText?: string;
  accentClass?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (data.length === 0) {
    return <p className="text-sm text-muted-foreground/70">{emptyText}</p>;
  }

  return (
    <ul className="space-y-1.5">
      {data.map((d) => {
        const pct = Math.round((d.value / max) * 100);
        return (
          <li key={d.key} className="flex items-center gap-3">
            <span className="w-32 shrink-0 truncate text-xs font-medium text-muted-foreground">
              {d.label}
              {d.hint ? <span className="ml-1 text-muted-foreground/60">· {d.hint}</span> : null}
            </span>
            <span className="relative h-5 flex-1 overflow-hidden rounded bg-muted">
              <span
                className={cn("absolute inset-y-0 left-0 rounded", accentClass)}
                style={{ width: `${pct}%` }}
              />
            </span>
            <span className="w-8 shrink-0 text-right text-sm font-semibold tabular-nums">
              {d.value}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
