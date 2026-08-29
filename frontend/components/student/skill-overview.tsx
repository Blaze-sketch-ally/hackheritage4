import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SkillChart } from "@/components/dashboard/skill-chart";
import type { SkillRadarPoint } from "@/lib/mock/student-dashboard";
import type { StudentSkill } from "@/lib/student/skills";

export function SkillOverview({ radar, studentSkills }: { radar: SkillRadarPoint[]; studentSkills: StudentSkill[] }) {
  const preview = studentSkills.slice(0, 6);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Skill Overview</CardTitle>
        <CardDescription>
          Chart is demo data — real assessment scoring lands in a later phase. The list reflects your actual skills.
        </CardDescription>
        <CardAction>
          <Button variant="ghost" size="sm" render={<Link href="/student/skills" />} nativeButton={false}>
            View All
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-2">
        <SkillChart data={radar} />
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
                <Badge variant="outline">{studentSkill.proficiency_level}</Badge>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
