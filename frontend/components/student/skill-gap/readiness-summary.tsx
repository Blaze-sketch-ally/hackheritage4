import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { SkillGapSummary } from "@/types/skill-gap";

/** Every value here comes straight from the backend's SkillGapJobRoleResponse
 * -- readiness_percentage/summary are never recomputed client-side. */
export function ReadinessSummary({
  readinessPercentage,
  summary,
}: {
  readinessPercentage: number;
  summary: SkillGapSummary;
}) {
  const stats = [
    { label: "Matched Skills", value: summary.matched },
    { label: "Needs Improvement", value: summary.needs_improvement },
    { label: "Missing Skills", value: summary.missing },
    { label: "Unverified Skills", value: summary.unverified },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <Card className="xl:col-span-1">
        <CardContent className="space-y-2">
          <p className="text-sm text-muted-foreground">Career Readiness</p>
          <p className="text-2xl font-semibold tracking-tight">{readinessPercentage}%</p>
          <Progress value={readinessPercentage} />
        </CardContent>
      </Card>
      {stats.map((stat) => (
        <Card key={stat.label}>
          <CardContent className="space-y-1">
            <p className="text-sm text-muted-foreground">{stat.label}</p>
            <p className="text-2xl font-semibold tracking-tight">{stat.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
