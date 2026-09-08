import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarList } from "@/components/industry/analytics/bar-list";
import type { StudentInsights as StudentInsightsData } from "@/types/institution-analytics";

export function StudentInsights({ insights }: { insights: StudentInsightsData }) {
  const skillsData = insights.top_skills.map((s) => ({
    key: s.skill_name,
    label: s.skill_name,
    value: s.student_count,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Student Insights</CardTitle>
        <p className="text-xs text-muted-foreground">Among students linked to your institution.</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-muted/50 px-3 py-2">
            <p className="text-xl font-semibold tabular-nums">{insights.students_with_no_applications}</p>
            <p className="text-[11px] text-muted-foreground">No applications yet</p>
          </div>
          <div className="rounded-lg bg-muted/50 px-3 py-2">
            <p className="text-xl font-semibold tabular-nums">{insights.students_actively_applying}</p>
            <p className="text-[11px] text-muted-foreground">Actively applying</p>
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">Top skills</p>
          <BarList data={skillsData} emptyText="No skills recorded yet." accentClass="bg-violet-500/70" />
        </div>

        <div className="border-t pt-3 text-xs text-muted-foreground">
          {insights.assessments_completed > 0 ? (
            <p>
              <span className="font-semibold text-foreground tabular-nums">
                {insights.assessments_completed}
              </span>{" "}
              assessment{insights.assessments_completed === 1 ? "" : "s"} completed, averaging{" "}
              <span className="font-semibold text-foreground tabular-nums">
                {insights.average_assessment_percentage}%
              </span>
              .
            </p>
          ) : (
            <p>No completed assessments yet.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
