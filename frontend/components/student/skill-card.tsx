"use client";

import Link from "next/link";
import { CheckCircle2, Circle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { StudentSkill } from "@/lib/student/skills";
import type { Assessment } from "@/types/assessment";

const PROFICIENCY_ACCENT: Record<StudentSkill["proficiency_level"], string> = {
  Beginner: "bg-muted text-muted-foreground",
  Intermediate: "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400",
  Advanced: "border-indigo-500/30 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  Expert: "border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-400",
};

export function SkillCard({
  studentSkill,
  matchingAssessment,
  onEdit,
  onDelete,
}: {
  studentSkill: StudentSkill;
  /** The active assessment for this exact (skill_id, proficiency_level)
   * pair, if one exists -- exact match only, per the same rule
   * score_assessment_attempt() enforces server-side for verification
   * itself: a Python Advanced assessment can never appear here for a
   * declared Python Intermediate skill, or vice versa. Undefined means
   * none exists yet -- never fabricate one. */
  matchingAssessment?: Assessment;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 space-y-0.5">
            <p className="truncate text-sm font-medium">{studentSkill.skill.name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {studentSkill.skill.category?.name ?? "Uncategorized"}
            </p>
          </div>
          <Badge variant="outline" className={PROFICIENCY_ACCENT[studentSkill.proficiency_level]}>
            {studentSkill.proficiency_level}
          </Badge>
        </div>

        <div className="flex items-center gap-1.5 text-xs">
          {studentSkill.is_verified ? (
            <>
              <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
              <span className="text-emerald-600 dark:text-emerald-400">Verified</span>
            </>
          ) : (
            <>
              <Circle className="size-3.5 text-muted-foreground" aria-hidden="true" />
              <span className="text-muted-foreground">Not Verified</span>
            </>
          )}
        </div>

        {matchingAssessment ? (
          <Button
            size="sm"
            className="w-full"
            render={<Link href={`/student/assessment/${matchingAssessment.id}`} />}
            nativeButton={false}
          >
            {studentSkill.is_verified
              ? "Take Assessment"
              : `Take ${studentSkill.proficiency_level} Assessment`}
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground">Assessment not available yet.</p>
        )}

        <div className="flex gap-2 pt-1">
          <Button variant="outline" size="sm" className="flex-1" onClick={onEdit}>
            Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1 text-destructive hover:text-destructive"
            onClick={onDelete}
          >
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
