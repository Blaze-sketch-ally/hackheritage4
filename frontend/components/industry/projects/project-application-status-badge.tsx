import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  PROJECT_APPLICATION_STATUS_LABELS,
  type ProjectApplicationStatus,
} from "@/types/project-application";

const STATUS_CLASSES: Record<ProjectApplicationStatus, string> = {
  APPLIED: "bg-muted text-muted-foreground",
  SHORTLISTED: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  SELECTED: "bg-green-600/10 text-green-700 dark:text-green-400",
  ACTIVE: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
  REJECTED: "bg-destructive/10 text-destructive",
  WITHDRAWN: "bg-foreground/5 text-muted-foreground",
  COMPLETED: "bg-violet-500/10 text-violet-700 dark:text-violet-400",
};

export function ProjectApplicationStatusBadge({
  status,
  className,
}: {
  status: ProjectApplicationStatus;
  className?: string;
}) {
  return (
    <Badge variant="ghost" className={cn(STATUS_CLASSES[status], className)}>
      {PROJECT_APPLICATION_STATUS_LABELS[status]}
    </Badge>
  );
}
