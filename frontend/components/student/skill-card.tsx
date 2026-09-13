"use client";

import Link from "next/link";
import { AlertCircle, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { StudentSkill } from "@/lib/student/skills";
import type { Assessment, AttemptHistoryItem } from "@/types/assessment";

/** Same lookup states student-skills-view.tsx tracks for the whole page's
 * assessment/attempt fetch -- "loading" and "error" must never be rendered
 * as if they were "ready" with nothing found, or this card would tell a
 * student "Assessment not available yet." while the lookup is still in
 * flight or has actually failed. */
type LookupStatus = "loading" | "error" | "ready";

const PROFICIENCY_ACCENT: Record<StudentSkill["proficiency_level"], string> = {
  Beginner: "bg-muted text-muted-foreground",
  Intermediate: "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400",
  Advanced: "border-indigo-500/30 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  Expert: "border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-400",
};

export function SkillCard({
  studentSkill,
  lookupStatus = "ready",
  matchingAssessment,
  latestAttempt,
  onEdit,
  onDelete,
}: {
  studentSkill: StudentSkill;
  /** Status of the page-wide assessment/attempt-history fetch this card's
   * action depends on. Defaults to "ready" so every existing call site
   * (and every existing test) that doesn't pass it keeps behaving exactly
   * as before -- only student-skills-view.tsx needs to pass the real,
   * in-flight status. */
  lookupStatus?: LookupStatus;
  /** The active assessment for this exact (skill_id, proficiency_level)
   * pair, if one exists -- exact match only, per the same rule
   * score_assessment_attempt() enforces server-side for verification
   * itself: a Python Advanced assessment can never appear here for a
   * declared Python Intermediate skill, or vice versa. Undefined means
   * none exists yet -- never fabricate one. Only meaningful when
   * lookupStatus is "ready". */
  matchingAssessment?: Assessment;
  /** The caller's own most recent attempt at `matchingAssessment` (same
   * exact skill_id + difficulty match), if any -- lets an unverified skill
   * that was already attempted show its real last outcome ("In Progress" /
   * "Failed") instead of looking untouched. Reuses the exact same
   * status/passed terminology assessment-history-view.tsx already renders
   * ("In Progress", "Failed") rather than inventing a new vocabulary. */
  latestAttempt?: AttemptHistoryItem;
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

        <SkillAssessmentAction
          studentSkill={studentSkill}
          lookupStatus={lookupStatus}
          matchingAssessment={matchingAssessment}
          latestAttempt={latestAttempt}
        />

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

function SkillAssessmentAction({
  studentSkill,
  lookupStatus,
  matchingAssessment,
  latestAttempt,
}: {
  studentSkill: StudentSkill;
  lookupStatus: LookupStatus;
  matchingAssessment?: Assessment;
  latestAttempt?: AttemptHistoryItem;
}) {
  // STATE: still checking whether an assessment exists -- never claim
  // "not available yet" while the fetch is still in flight.
  if (lookupStatus === "loading") {
    return (
      <Button size="sm" className="w-full" disabled aria-label="Checking assessment availability">
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> Checking assessment…
      </Button>
    );
  }

  // STATE: the lookup itself failed -- distinct from "no assessment
  // exists", which is a legitimate, honest empty state below.
  if (lookupStatus === "error") {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
        Couldn&apos;t check assessment status. Refresh the page to try again.
      </p>
    );
  }

  // STATE: no assessment exists yet for this exact (skill, level) pair --
  // an honest empty state, never a misleading button that leads nowhere.
  if (!matchingAssessment) {
    return <p className="text-xs text-muted-foreground">Assessment not available yet.</p>;
  }

  const assessmentHref = `/student/assessment/${matchingAssessment.id}`;

  // STATE: already verified -- offer to view the same assessment (its
  // detail page also serves as the "retake" screen) rather than the
  // level-specific verification action, which no longer applies.
  if (studentSkill.is_verified) {
    return (
      <Button size="sm" className="w-full" render={<Link href={assessmentHref} />} nativeButton={false}>
        View Assessment
      </Button>
    );
  }

  // STATE: an attempt is already IN_PROGRESS -- same term
  // assessment-history-view.tsx's StatusBadge uses. Resuming is handled by
  // the assessment detail page itself (GET .../attempts/current).
  if (latestAttempt?.status === "IN_PROGRESS") {
    return (
      <div className="space-y-1">
        <p className="text-xs text-muted-foreground">Attempt in progress</p>
        <Button size="sm" className="w-full" render={<Link href={assessmentHref} />} nativeButton={false}>
          Resume Assessment
        </Button>
      </div>
    );
  }

  // STATE: the most recent COMPLETED attempt didn't pass -- same "Failed"
  // term assessment-history-view.tsx's StatusBadge uses. Still not
  // verified, but the student can see they've already tried and retake.
  if (latestAttempt?.status === "COMPLETED" && latestAttempt.passed === false) {
    return (
      <div className="space-y-1">
        <p className="text-xs text-destructive">Last attempt: Failed</p>
        <Button size="sm" className="w-full" render={<Link href={assessmentHref} />} nativeButton={false}>
          Retake Assessment
        </Button>
      </div>
    );
  }

  // STATE: assessment available, never attempted (or only ABANDONED) --
  // the default action. Labeled "Verify Skill" rather than "Take {Level}
  // Assessment" because the product-level purpose of this button is
  // verifying the skill on the student's profile, not just taking a test --
  // the destination is unchanged, still the exact (skill_id,
  // proficiency_level) match.
  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground">Pass the assessment to verify this skill.</p>
      <Button size="sm" className="w-full" render={<Link href={assessmentHref} />} nativeButton={false}>
        Verify Skill
      </Button>
    </div>
  );
}
