import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress, ProgressIndicator, ProgressTrack } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { MatchSkill, OpportunityMatch, SkillMatchStatus } from "@/types/student-opportunity";

const RECOMMENDATION_LABEL: Record<OpportunityMatch["recommendation"], string> = {
  STRONG: "Strong match",
  GOOD: "Good match",
  PARTIAL: "Partial match",
  LOW: "Low match",
};

/** The student's own advisory skill fit for one opportunity. Same
 * deterministic result the Industry applicant-match view consumes
 * (backend/app/services/match_service.py) -- rendered read-only. */
export function SkillMatchCard({ match }: { match: OpportunityMatch }) {
  const rows: MatchSkill[] = [
    ...match.matched_skills,
    ...match.needs_improvement_skills,
    ...match.missing_skills,
  ];
  const hasRequirements = match.required_count > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Your Match</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">{RECOMMENDATION_LABEL[match.recommendation]}</span>
            <span className="font-semibold tabular-nums">{match.score}%</span>
          </div>
          <Progress value={match.score}>
            <ProgressTrack>
              <ProgressIndicator />
            </ProgressTrack>
          </Progress>
          {hasRequirements && (
            <p className="text-xs text-muted-foreground">
              {match.skill_coverage} required skills covered
            </p>
          )}
        </div>

        {!hasRequirements ? (
          <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
            This posting lists no required skills, so there is nothing to match against yet.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Skill</TableHead>
                <TableHead>Required</TableHead>
                <TableHead>You</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((skill) => (
                <TableRow key={skill.skill_id}>
                  <TableCell className="font-medium">{skill.skill_name}</TableCell>
                  <TableCell className="text-muted-foreground">{skill.required_level}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {skill.candidate_has ? skill.candidate_level ?? "—" : "—"}
                  </TableCell>
                  <TableCell>
                    <MatchStatusBadge status={skill.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function MatchStatusBadge({ status }: { status: SkillMatchStatus }) {
  if (status === "MATCHED")
    return <Badge className="bg-emerald-600 text-white hover:bg-emerald-600">Matched</Badge>;
  if (status === "NEEDS_IMPROVEMENT")
    return <Badge className="bg-amber-500 text-white hover:bg-amber-500">Improve</Badge>;
  return <Badge variant="destructive">Missing</Badge>;
}
