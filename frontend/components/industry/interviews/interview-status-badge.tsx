import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { INTERVIEW_STATUS_LABELS, type InterviewStatus } from "@/types/interview";

const STATUS_CLASSES: Record<InterviewStatus, string> = {
  SCHEDULED: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  COMPLETED: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  CANCELLED: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
};

export function InterviewStatusBadge({
  status,
  className,
}: {
  status: InterviewStatus;
  className?: string;
}) {
  return (
    <Badge variant="ghost" className={cn(STATUS_CLASSES[status], className)}>
      {INTERVIEW_STATUS_LABELS[status]}
    </Badge>
  );
}
