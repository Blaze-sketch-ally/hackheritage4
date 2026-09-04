import { Badge } from "@/components/ui/badge";

/**
 * The five workspace_submissions.submission_status values
 * (database/migrations/039_workspace_submissions_completion.sql). Phase 5
 * only ever shows SUBMITTED (every new attempt starts there); the other
 * values appear once Phase 6 reviews land, so they are styled now.
 */
type Style = { className?: string; variant?: "outline" | "secondary" | "destructive" };

const STATUS_STYLE: Record<string, Style> = {
  SUBMITTED: { className: "bg-sky-600 text-white hover:bg-sky-600" },
  UNDER_REVIEW: { className: "bg-indigo-600 text-white hover:bg-indigo-600" },
  REVISION_REQUESTED: { className: "bg-amber-500 text-white hover:bg-amber-500" },
  ACCEPTED: { className: "bg-emerald-600 text-white hover:bg-emerald-600" },
  REJECTED: { variant: "destructive" },
};

const STATUS_LABEL: Record<string, string> = {
  SUBMITTED: "Submitted",
  UNDER_REVIEW: "Under review",
  REVISION_REQUESTED: "Revision requested",
  ACCEPTED: "Accepted",
  REJECTED: "Rejected",
};

export function SubmissionStatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLE[status] ?? { variant: "outline" as const };
  return (
    <Badge variant={style.variant} className={style.className}>
      {STATUS_LABEL[status] ?? status}
    </Badge>
  );
}
