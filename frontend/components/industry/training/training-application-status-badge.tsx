import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  TRAINING_APPLICATION_STATUS_LABELS,
  type TrainingApplicationStatus,
} from "@/types/training-application";

const STATUS_CLASSES: Record<TrainingApplicationStatus, string> = {
  APPLIED: "bg-muted text-muted-foreground",
  ACCEPTED: "bg-green-600/10 text-green-700 dark:text-green-400",
  REJECTED: "bg-destructive/10 text-destructive",
  WITHDRAWN: "bg-foreground/5 text-muted-foreground",
  COMPLETED: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
};

export function TrainingApplicationStatusBadge({
  status,
  className,
}: {
  status: TrainingApplicationStatus;
  className?: string;
}) {
  return (
    <Badge variant="ghost" className={cn(STATUS_CLASSES[status], className)}>
      {TRAINING_APPLICATION_STATUS_LABELS[status]}
    </Badge>
  );
}
