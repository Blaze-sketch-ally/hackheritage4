import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { APPLICATION_STATUS_LABELS, type ApplicationStatus } from "@/types/application";

const STATUS_CLASSES: Record<ApplicationStatus, string> = {
  APPLIED: "bg-muted text-muted-foreground",
  UNDER_REVIEW: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
  SHORTLISTED: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  INTERVIEW_SCHEDULED: "bg-violet-500/10 text-violet-700 dark:text-violet-400",
  SELECTED: "bg-green-600/10 text-green-700 dark:text-green-400",
  REJECTED: "bg-destructive/10 text-destructive",
  WITHDRAWN: "bg-foreground/5 text-muted-foreground",
};

export function ApplicationStatusBadge({
  status,
  className,
}: {
  status: ApplicationStatus;
  className?: string;
}) {
  return (
    <Badge variant="ghost" className={cn(STATUS_CLASSES[status], className)}>
      {APPLICATION_STATUS_LABELS[status]}
    </Badge>
  );
}
