import Link from "next/link";
import { redirect } from "next/navigation";
import { CheckCircle2, Clock3, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RetryScoringButton } from "@/components/student/assessments/retry-scoring-button";
import { createClient } from "@/lib/supabase/server";
import { fetchAssessmentById, fetchAttemptById, fetchLatestAttempt, fetchMyAnswers } from "@/lib/student/assessments";

function formatDateTime(value: string | null) {
  if (!value) return null;
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default async function AssessmentResultPage({
  params,
  searchParams,
}: {
  params: Promise<{ assessmentId: string }>;
  searchParams: Promise<{ attemptId?: string }>;
}) {
  const { assessmentId } = await params;
  const { attemptId } = await searchParams;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const assessment = await fetchAssessmentById(supabase, assessmentId);
  if (!assessment) redirect("/student/assessments");

  // RLS (auth.uid() = student_id) means an attemptId belonging to another
  // student simply resolves to null here, never another student's data.
  const attempt = attemptId
    ? await fetchAttemptById(supabase, attemptId)
    : await fetchLatestAttempt(supabase, user.id, assessmentId);

  if (!attempt || attempt.student_id !== user.id || attempt.assessment_id !== assessmentId) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-16 text-center">
        <p className="text-sm font-medium">No result available.</p>
        <p className="text-sm text-muted-foreground">You haven&apos;t attempted this assessment yet.</p>
        <Button render={<Link href={`/student/assessments/${assessmentId}`} />} nativeButton={false}>
          View Assessment
        </Button>
      </div>
    );
  }

  // Correct/incorrect counts are derived from the caller's own persisted
  // assessment_answers.is_correct — never from the answer key directly,
  // and only meaningful once the attempt is COMPLETED (is_correct is
  // null on every answer until the backend scores it).
  const answers = attempt.status === "COMPLETED" ? await fetchMyAnswers(supabase, attempt.id) : [];
  const correctCount = answers.filter((a) => a.is_correct === true).length;
  const incorrectCount = answers.filter((a) => a.is_correct === false).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{assessment.title} — Result</h1>
        {assessment.skill ? <p className="text-sm text-muted-foreground">{assessment.skill.name}</p> : null}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Result</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {attempt.status === "COMPLETED" ? (
            <>
              <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="size-5" aria-hidden="true" />
                <span className="text-sm font-medium">Completed</span>
              </div>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                <div>
                  <p className="text-xs text-muted-foreground">Score</p>
                  <p className="text-2xl font-semibold tracking-tight">{attempt.score ?? "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Total Marks</p>
                  <p className="text-2xl font-semibold tracking-tight">{attempt.total_marks ?? "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Percentage</p>
                  <p className="text-2xl font-semibold tracking-tight">
                    {attempt.percentage !== null ? `${attempt.percentage}%` : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Correct</p>
                  <p className="text-2xl font-semibold tracking-tight text-emerald-600 dark:text-emerald-400">
                    {correctCount}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Incorrect</p>
                  <p className="text-2xl font-semibold tracking-tight text-destructive">{incorrectCount}</p>
                </div>
              </div>
              {formatDateTime(attempt.submitted_at) ? (
                <p className="text-xs text-muted-foreground">Submitted {formatDateTime(attempt.submitted_at)}</p>
              ) : null}
            </>
          ) : attempt.status === "ABANDONED" ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <XCircle className="size-5" aria-hidden="true" />
              <span className="text-sm font-medium">This attempt was abandoned.</span>
            </div>
          ) : attempt.submitted_at ? (
            <div className="space-y-3">
              <div className="flex items-start gap-2">
                <Clock3 className="mt-0.5 size-5 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
                <div>
                  <p className="text-sm font-medium">Submitted — awaiting scoring.</p>
                  <p className="text-sm text-muted-foreground">
                    Your answers have been recorded. Submitted {formatDateTime(attempt.submitted_at)}.
                  </p>
                </div>
              </div>
              <RetryScoringButton attemptId={attempt.id} />
            </div>
          ) : (
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Clock3 className="size-5" aria-hidden="true" />
                <span className="text-sm font-medium">This attempt is still in progress.</span>
              </div>
              <Button
                variant="outline"
                render={<Link href={`/student/assessments/${assessmentId}/take`} />}
                nativeButton={false}
              >
                Continue
              </Button>
            </div>
          )}

          <Badge variant="outline">{attempt.status.replace("_", " ")}</Badge>
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <Button variant="outline" render={<Link href="/student/assessments" />} nativeButton={false}>
          Back to Assessments
        </Button>
        <Button variant="outline" render={<Link href="/student/assessments/history" />} nativeButton={false}>
          View History
        </Button>
      </div>
    </div>
  );
}
