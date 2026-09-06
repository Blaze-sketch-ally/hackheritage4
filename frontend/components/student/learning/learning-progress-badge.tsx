import { BookmarkCheck, CircleDashed, CircleDot } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { PROGRESS_LABEL, type LearningProgressStatus } from "@/types/student-learning";

type Style = { className: string; icon: typeof CircleDot };

const STATUS_STYLE: Record<LearningProgressStatus, Style> = {
  SAVED: { className: "bg-sky-600 text-white hover:bg-sky-600", icon: BookmarkCheck },
  IN_PROGRESS: { className: "bg-amber-500 text-white hover:bg-amber-500", icon: CircleDot },
  COMPLETED: { className: "bg-emerald-600 text-white hover:bg-emerald-600", icon: CircleDashed },
};

/** Renders the student's own progress status on a learning resource.
 * `null`/undefined -> "Not started" (a neutral outline badge). */
export function LearningProgressBadge({ status }: { status: LearningProgressStatus | null | undefined }) {
  if (!status) {
    return (
      <Badge variant="outline" className="gap-1 text-muted-foreground">
        <CircleDashed className="size-3" aria-hidden="true" />
        Not started
      </Badge>
    );
  }
  const style = STATUS_STYLE[status] ?? {
    className: "",
    icon: CircleDot,
  };
  const Icon = style.icon;
  return (
    <Badge className={`gap-1 ${style.className}`}>
      <Icon className="size-3" aria-hidden="true" />
      {PROGRESS_LABEL[status] ?? status}
    </Badge>
  );
}
