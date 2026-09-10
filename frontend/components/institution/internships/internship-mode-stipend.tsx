import { Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ModeCount, StipendStats } from "@/types/institution-internship";

/** Mode distribution + stipend statistics (Phase 7, Part 12). Stipend is
 * grouped by currency -- amounts in different currencies are never
 * averaged together (see `stipend.note`, always shown). */
export function InternshipModeStipend({ modes, stipend }: { modes: ModeCount[]; stipend: StipendStats }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Internship Mode</CardTitle>
        </CardHeader>
        <CardContent>
          {modes.length === 0 ? (
            <p className="text-sm text-muted-foreground/70">No mode data yet.</p>
          ) : (
            <ul className="space-y-1.5">
              {modes.map((m) => (
                <li key={m.mode} className="flex items-center justify-between text-sm">
                  <span>{m.mode}</span>
                  <span className="font-semibold tabular-nums">{m.count}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Stipend</CardTitle>
          <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
            <Info className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
            {stipend.note}
          </p>
        </CardHeader>
        <CardContent>
          {!stipend.available ? (
            <p className="text-sm text-muted-foreground/70">No stipend data available.</p>
          ) : (
            <ul className="space-y-2">
              {stipend.by_currency.map((row) => (
                <li key={row.currency} className="rounded-lg bg-muted/50 px-3 py-2 text-sm">
                  <div className="flex items-center justify-between font-medium">
                    <span>{row.currency}</span>
                    <span>{row.internship_count} internships</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Avg {row.average_stipend.toLocaleString()} · Min {row.min_stipend.toLocaleString()} · Max{" "}
                    {row.max_stipend.toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
