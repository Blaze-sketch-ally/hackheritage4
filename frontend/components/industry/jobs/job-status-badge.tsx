import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { JOB_STATUS_LABELS, type JobStatus } from "@/types/job";

const STATUS_CLASSES: Record<JobStatus, string> = {
  DRAFT: "bg-muted text-muted-foreground",
  PUBLISHED: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  CLOSED: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  ARCHIVED: "bg-foreground/5 text-muted-foreground",
};

export function JobStatusBadge({ status, className }: { status: JobStatus; className?: string }) {
  return (
    <Badge variant="ghost" className={cn(STATUS_CLASSES[status], className)}>
      {JOB_STATUS_LABELS[status]}
    </Badge>
  );
}
