import { Badge } from "@/components/ui/badge";
import type { AttemptDisplayStatus } from "@/lib/student/assessment";

const LABEL: Record<AttemptDisplayStatus, string> = {
  NOT_ATTEMPTED: "Not Attempted",
  IN_PROGRESS: "In Progress",
  PASSED: "Passed",
  NOT_PASSED: "Not Passed",
  COMPLETED: "Completed",
  ABANDONED: "Abandoned",
};

const CLASS_NAME: Partial<Record<AttemptDisplayStatus, string>> = {
  PASSED: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  NOT_PASSED: "border-destructive/30 bg-destructive/10 text-destructive",
};

/** One canonical badge for an assessment's attempt state -- shared by the
 * Assessment list (which also needs NOT_ATTEMPTED, a state History never
 * has, since every History row already IS an attempt) and Assessment
 * History, so the two pages never drift into different wording for the
 * same underlying attempt. */
export function AttemptStatusBadge({ status }: { status: AttemptDisplayStatus }) {
  return (
    <Badge variant="outline" className={CLASS_NAME[status]}>
      {LABEL[status]}
    </Badge>
  );
}
