import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  WORKSHOP_APPLICATION_STATUS_LABELS,
  type WorkshopApplicationStatus,
} from "@/types/workshop-application";

const STATUS_CLASSES: Record<WorkshopApplicationStatus, string> = {
  APPLIED: "bg-muted text-muted-foreground",
  ACCEPTED: "bg-green-600/10 text-green-700 dark:text-green-400",
  REJECTED: "bg-destructive/10 text-destructive",
  WITHDRAWN: "bg-foreground/5 text-muted-foreground",
  COMPLETED: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
};

export function WorkshopApplicationStatusBadge({
  status,
  className,
}: {
  status: WorkshopApplicationStatus;
  className?: string;
}) {
  return (
    <Badge variant="ghost" className={cn(STATUS_CLASSES[status], className)}>
      {WORKSHOP_APPLICATION_STATUS_LABELS[status]}
    </Badge>
  );
}
