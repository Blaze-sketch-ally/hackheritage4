import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { COLLABORATION_STATUS_LABELS, type CollaborationStatus } from "@/types/industry-collaboration";

const STATUS_CLASSES: Record<CollaborationStatus, string> = {
  DRAFT: "bg-muted text-muted-foreground",
  SENT: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
  ACCEPTED: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  REJECTED: "bg-destructive/10 text-destructive",
  ACTIVE: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  COMPLETED: "bg-foreground/5 text-muted-foreground",
  CANCELLED: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
};

export function CollaborationStatusBadge({
  status,
  className,
}: {
  status: CollaborationStatus;
  className?: string;
}) {
  return (
    <Badge variant="ghost" className={cn(STATUS_CLASSES[status], className)}>
      {COLLABORATION_STATUS_LABELS[status]}
    </Badge>
  );
}
