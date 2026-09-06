import { Badge } from "@/components/ui/badge";
import { STATUS_LABEL, type StudentApplicationStatus } from "@/types/student-opportunity";

type Style = { className?: string; variant?: "outline" | "destructive" | "secondary" };

// Covers all SEVEN live applications.status values
// (database/migrations/020_applications.sql) -- the student never sets any
// of these; they are shown exactly as the owning Industry account left
// them, with a friendly label.
const STATUS_STYLE: Record<StudentApplicationStatus, Style> = {
  APPLIED: { variant: "secondary" },
  UNDER_REVIEW: { className: "bg-sky-600 text-white hover:bg-sky-600" },
  SHORTLISTED: { className: "bg-indigo-600 text-white hover:bg-indigo-600" },
  INTERVIEW_SCHEDULED: { className: "bg-amber-500 text-white hover:bg-amber-500" },
  SELECTED: { className: "bg-emerald-600 text-white hover:bg-emerald-600" },
  REJECTED: { variant: "destructive" },
  WITHDRAWN: { variant: "outline" },
};

export function ApplicationStatusBadge({ status }: { status: StudentApplicationStatus }) {
  // Defensive: an unrecognised value still renders rather than crashing.
  const style = STATUS_STYLE[status] ?? { variant: "outline" as const };
  const label = STATUS_LABEL[status] ?? status;
  return (
    <Badge variant={style.variant} className={style.className}>
      {label}
    </Badge>
  );
}
