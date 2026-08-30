import Link from "next/link";
import { redirect } from "next/navigation";
import { History } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/common/empty-state";
import { createClient } from "@/lib/supabase/server";
import { fetchMyAttempts, type AttemptStatus } from "@/lib/student/assessments";

const STATUS_ACCENT: Record<AttemptStatus, string> = {
  IN_PROGRESS: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  COMPLETED: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  ABANDONED: "bg-muted text-muted-foreground",
};

function formatDateTime(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default async function AssessmentHistoryPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const attempts = await fetchMyAttempts(supabase, user.id);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Assessment History</h1>
        <p className="text-sm text-muted-foreground">Your past and in-progress assessment attempts.</p>
      </div>

      {attempts.length === 0 ? (
        <EmptyState icon={History} title="You haven't attempted any assessments yet." />
      ) : (
        <div className="space-y-3">
          {attempts.map((attempt) => {
            const title = attempt.assessment?.title ?? "Assessment";
            const resultHref = `/student/assessments/${attempt.assessment_id}/result?attemptId=${attempt.id}`;
            const actionHref =
              attempt.status === "IN_PROGRESS"
                ? `/student/assessments/${attempt.assessment_id}/take`
                : resultHref;
            const actionLabel = attempt.status === "IN_PROGRESS" ? "Continue" : "View Result";

            return (
              <Card key={attempt.id}>
                <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-medium">{title}</p>
                      <Badge variant="outline" className={STATUS_ACCENT[attempt.status]}>
                        {attempt.status.replace("_", " ")}
                      </Badge>
                    </div>
                    {attempt.assessment?.skill ? (
                      <p className="text-xs text-muted-foreground">{attempt.assessment.skill.name}</p>
                    ) : null}
                    <p className="text-xs text-muted-foreground">
                      Started {formatDateTime(attempt.started_at)}
                      {attempt.submitted_at ? ` · Submitted ${formatDateTime(attempt.submitted_at)}` : ""}
                    </p>
                    {attempt.status === "COMPLETED" && attempt.percentage !== null ? (
                      <p className="text-xs font-medium text-foreground">
                        Score: {attempt.score} / {attempt.total_marks} ({attempt.percentage}%)
                      </p>
                    ) : null}
                  </div>
                  <Button variant="outline" render={<Link href={actionHref} />} nativeButton={false}>
                    {actionLabel}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
