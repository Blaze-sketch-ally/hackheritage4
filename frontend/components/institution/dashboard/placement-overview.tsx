import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarList } from "@/components/industry/analytics/bar-list";
import type { StudentMetrics } from "@/types/institution-analytics";

/** "Other" here means students linked to this institution who have not
 * applied to anything yet (not_participating) — distinct from "Unplaced"
 * (actively applying, no offer yet). No historical trend is shown: the
 * schema records only current status, not when it changed. */
export function PlacementOverview({ metrics }: { metrics: StudentMetrics }) {
  const data = [
    { key: "placed", label: "Placed", value: metrics.placed },
    { key: "unplaced", label: "Unplaced", value: metrics.unplaced_active },
    { key: "other", label: "Other (no applications)", value: metrics.not_participating },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Placement Overview</CardTitle>
        <p className="text-xs text-muted-foreground">
          Among students linked to your institution right now.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <BarList data={data} emptyText="No linked students yet." accentClass="bg-emerald-500/70" />
        <div className="space-y-1 border-t pt-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Placement rate</span>
            <span className="font-semibold text-foreground tabular-nums">
              {metrics.placement_percentage != null ? `${metrics.placement_percentage}%` : "—"}
            </span>
          </div>
          <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-emerald-500/70"
              style={{ width: `${metrics.placement_percentage ?? 0}%` }}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
