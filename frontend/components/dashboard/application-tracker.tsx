import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ApplicationStage } from "@/lib/mock/student-dashboard";

const STAGE_ACCENTS = ["bg-indigo-500", "bg-blue-500", "bg-violet-500", "bg-amber-500", "bg-emerald-500"];

export function ApplicationTracker({
  stages,
  title = "Application Tracker",
}: {
  stages: ApplicationStage[];
  title?: string;
}) {
  const max = Math.max(...stages.map((s) => s.count), 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {stages.map((stage, i) => (
          <div key={stage.label} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{stage.label}</span>
              <span className="font-medium">{stage.count}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn("h-full rounded-full transition-all", STAGE_ACCENTS[i % STAGE_ACCENTS.length])}
                style={{ width: `${(stage.count / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
