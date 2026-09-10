import { Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import type { SkillGapAnalytics } from "@/types/institution-analytics-report";

/**
 * Skill Gaps (Phase 6, Part 14/15) -- deliberately descriptive, never
 * predictive. "High demand" / "Low coverage" are two small documented
 * constant thresholds (see `skill_gaps.note`, always rendered here),
 * never an opaque AI score, and never labeled "critical" -- no such rule
 * is defined. When no currently-PUBLISHED job declares any required
 * skill, the comparison is shown as explicitly unavailable rather than
 * a misleading "no gaps found".
 */
export function SkillGapTable({ skillGaps }: { skillGaps: SkillGapAnalytics }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Skill Gaps</CardTitle>
        <p className="text-xs text-muted-foreground">{skillGaps.note}</p>
      </CardHeader>
      <CardContent>
        {!skillGaps.available ? (
          <EmptyState
            icon={Sparkles}
            title="Skill-demand comparison unavailable"
            description="No currently-published job on the platform declares any required skill yet."
          />
        ) : skillGaps.items.length === 0 ? (
          <EmptyState icon={Sparkles} title="No comparable skills yet" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Skill</TableHead>
                <TableHead className="text-right">Job Demand</TableHead>
                <TableHead className="text-right">Student Coverage</TableHead>
                <TableHead>Indicator</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {skillGaps.items.map((item) => (
                <TableRow key={item.skill_name}>
                  <TableCell className="font-medium">{item.skill_name}</TableCell>
                  <TableCell className="text-right tabular-nums">{item.job_demand_count} jobs</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {item.student_coverage_count}
                    {item.student_coverage_percentage != null ? ` (${item.student_coverage_percentage}%)` : ""}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {item.high_demand ? (
                        <Badge variant="outline" className="border-amber-500/40 text-amber-700 dark:text-amber-400">
                          High demand
                        </Badge>
                      ) : null}
                      {item.low_coverage ? (
                        <Badge
                          variant="outline"
                          className="border-destructive/40 text-destructive"
                        >
                          Low coverage
                        </Badge>
                      ) : null}
                    </div>
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
