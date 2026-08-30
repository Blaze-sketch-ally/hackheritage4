"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Clock, ListChecks, Play, RotateCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormError } from "@/components/auth/form-error";
import { createClient } from "@/lib/supabase/client";
import {
  getAssessmentErrorMessage,
  startAttempt,
  type Assessment,
  type AssessmentAttempt,
} from "@/lib/student/assessments";

const DIFFICULTY_ACCENT: Record<Assessment["difficulty"], string> = {
  Beginner: "bg-muted text-muted-foreground",
  Intermediate: "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400",
  Advanced: "border-indigo-500/30 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  Expert: "border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-400",
};

export function AssessmentDetailView({
  studentId,
  assessment,
  existingAttempt,
}: {
  studentId: string;
  assessment: Assessment;
  existingAttempt: AssessmentAttempt | null;
}) {
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    if (existingAttempt) {
      router.push(`/student/assessments/${assessment.id}/take`);
      return;
    }

    setStarting(true);
    setError(null);
    try {
      const supabase = createClient();
      const { error: startError } = await startAttempt(supabase, studentId, assessment.id);
      // A 23505 here means another request already created the in-progress
      // attempt (e.g. a double click) — that's fine, the /take page
      // resolves the existing attempt itself either way.
      if (startError && startError.code !== "23505") {
        setError(getAssessmentErrorMessage(startError));
        return;
      }
      router.push(`/student/assessments/${assessment.id}/take`);
    } catch (err) {
      console.error("Start assessment failed:", err);
      setError(getAssessmentErrorMessage(err));
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{assessment.title}</h1>
        {assessment.skill ? <p className="text-sm text-muted-foreground">{assessment.skill.name}</p> : null}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle>Overview</CardTitle>
            <Badge variant="outline" className={DIFFICULTY_ACCENT[assessment.difficulty]}>
              {assessment.difficulty}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {assessment.description ? <p className="text-sm text-muted-foreground">{assessment.description}</p> : null}

          <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
            {assessment.duration_minutes ? (
              <span className="flex items-center gap-1.5">
                <Clock className="size-4" aria-hidden="true" />
                {assessment.duration_minutes} minutes
              </span>
            ) : null}
            {assessment.question_count ? (
              <span className="flex items-center gap-1.5">
                <ListChecks className="size-4" aria-hidden="true" />
                {assessment.question_count} questions
              </span>
            ) : null}
          </div>

          <FormError message={error} />

          <Button onClick={handleStart} disabled={starting} size="lg">
            {existingAttempt ? (
              <>
                <RotateCcw /> {starting ? "Loading..." : "Resume Assessment"}
              </>
            ) : (
              <>
                <Play /> {starting ? "Starting..." : "Start Assessment"}
              </>
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
