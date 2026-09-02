import Link from "next/link";
import { BadgeCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { summarizeSkills } from "@/lib/student/dashboard";
import { PROFICIENCY_LEVELS, type StudentSkill } from "@/lib/student/skills";

/**
 * A truthful overview of the student's own `student_skills`: how many
 * skills, how many are assessment-verified, and the proficiency
 * distribution. No fabricated "skill score" and no demo radar — every
 * number here is a direct count of the student's real skills.
 */
export function SkillOverview({ studentSkills }: { studentSkills: StudentSkill[] }) {
  const summary = summarizeSkills(studentSkills);
  const preview = studentSkills.slice(0, 6);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Skill Overview</CardTitle>
        <CardAction>
          <Button variant="ghost" size="sm" render={<Link href="/student/skills" />} nativeButton={false}>
            View All
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <div className="flex items-baseline gap-4">
            <div>
              <p className="text-2xl font-semibold tracking-tight tabular-nums">{summary.total}</p>
              <p className="text-xs text-muted-foreground">skills tracked</p>
            </div>
            <div>
              <p className="flex items-center gap-1 text-2xl font-semibold tracking-tight tabular-nums text-emerald-600 dark:text-emerald-400">
                <BadgeCheck className="size-5" aria-hidden="true" />
                {summary.verified}
              </p>
              <p className="text-xs text-muted-foreground">assessment-verified</p>
            </div>
          </div>

          {summary.total > 0 ? (
            <div className="space-y-2">
              {PROFICIENCY_LEVELS.map((level) => {
                const count = summary.byLevel[level];
                const pct = (count / summary.total) * 100;
                return (
                  <div key={level} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">{level}</span>
                      <span className="font-medium tabular-nums">{count}</span>
                    </div>
                    <Progress value={pct} />
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>

        <div className="space-y-2">
          {preview.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-8 text-center">
              <p className="text-sm text-muted-foreground">No skills added yet.</p>
              <Button size="sm" render={<Link href="/student/skills" />} nativeButton={false}>
                Add Your First Skill
              </Button>
            </div>
          ) : (
            preview.map((studentSkill) => (
              <div
                key={studentSkill.id}
                className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{studentSkill.skill.name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {studentSkill.skill.category?.name ?? "Uncategorized"}
                  </p>
                </div>
                <Badge variant={studentSkill.is_verified ? "default" : "outline"}>
                  {studentSkill.proficiency_level}
                </Badge>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
