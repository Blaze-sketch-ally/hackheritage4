import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress, ProgressIndicator, ProgressTrack } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { AlignmentStatus } from "@/types/career-role";
import type { OpportunityMatchSkill } from "@/types/opportunity";

/** Shared by the student opportunity detail page and the industry
 * applicant detail page (Phase 1N) -- same rendering shape as Phase
 * 1L's SkillGapResult table, reused rather than reimplemented, since
 * both consume the identical backend AlignmentStatus/skill-comparison
 * contract. `title` defaults to the student framing; the industry view
 * passes "Skill Alignment" instead -- the underlying data and table are
 * identical either way, never a second implementation. */
export function SkillMatchCard({
  overallScore,
  skills,
  title = "Your Match",
}: {
  overallScore: string;
  skills: OpportunityMatchSkill[];
  title?: string;
}) {
  const score = Number(overallScore);
  const hasAnyEvidence = skills.some((s) => s.status !== "NOT_ASSESSED");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Overall alignment</span>
            <span className="font-semibold tabular-nums">{score.toFixed(0)}%</span>
          </div>
          <Progress value={score}>
            <ProgressTrack>
              <ProgressIndicator />
            </ProgressTrack>
          </Progress>
        </div>

        {!hasAnyEvidence && (
          <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
            Complete an assessment to build your skill profile — the requirements below are shown either way.
          </p>
        )}

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Skill</TableHead>
              <TableHead className="text-right">You</TableHead>
              <TableHead className="text-right">Required</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {skills.map((skill) => (
              <TableRow key={skill.skill_id}>
                <TableCell className="font-medium">{skill.skill_name}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {skill.status === "NOT_ASSESSED" ? "—" : Number(skill.student_score).toFixed(0)}
                </TableCell>
                <TableCell className="text-right tabular-nums">{Number(skill.required_level).toFixed(0)}</TableCell>
                <TableCell>
                  <MatchStatusBadge status={skill.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export function MatchStatusBadge({ status }: { status: AlignmentStatus }) {
  if (status === "STRONG") return <Badge className="bg-emerald-600 text-white hover:bg-emerald-600">Strong</Badge>;
  if (status === "GAP") return <Badge variant="destructive">Gap</Badge>;
  return <Badge variant="outline">Not assessed</Badge>;
}
