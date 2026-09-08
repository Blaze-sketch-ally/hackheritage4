import { Badge } from "@/components/ui/badge";
import {
  JOB_TRAINING_ENROLLMENT_STATUS_LABEL,
  type JobTrainingEnrollmentStatus,
} from "@/types/job-training";

type Style = { className?: string; variant?: "outline" | "destructive" | "secondary" };

// database/migrations/040_job_training.sql -- job_training_enrollments.enrollment_status.
// The student never sets this. REVOKED is never rendered (the list omits
// it, the detail 404s) but is covered for completeness.
const STATUS_STYLE: Record<JobTrainingEnrollmentStatus, Style> = {
  ACTIVE: { className: "bg-emerald-600 text-white hover:bg-emerald-600" },
  COMPLETED: { className: "bg-sky-600 text-white hover:bg-sky-600" },
  REVOKED: { variant: "destructive" },
};

export function JobTrainingStatusBadge({ status }: { status: string }) {
  const key = status as JobTrainingEnrollmentStatus;
  const style = STATUS_STYLE[key] ?? { variant: "outline" as const };
  const label = JOB_TRAINING_ENROLLMENT_STATUS_LABEL[key] ?? status;
  return (
    <Badge variant={style.variant} className={style.className}>
      {label}
    </Badge>
  );
}
