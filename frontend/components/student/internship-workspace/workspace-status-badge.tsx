import { Badge } from "@/components/ui/badge";
import {
  WORKSPACE_STATUS_LABEL,
  type WorkspaceStatus,
} from "@/types/internship-workspace";

type Style = { className?: string; variant?: "outline" | "destructive" | "secondary" };

// Covers all six workspace_status values
// (database/migrations/038_internship_workspace.sql). The student never
// sets these directly except accept/decline; they are shown with a
// friendly label.
const STATUS_STYLE: Record<WorkspaceStatus, Style> = {
  PENDING_ACCEPTANCE: { className: "bg-amber-500 text-white hover:bg-amber-500" },
  ACCEPTED: { className: "bg-emerald-600 text-white hover:bg-emerald-600" },
  IN_PROGRESS: { className: "bg-indigo-600 text-white hover:bg-indigo-600" },
  COMPLETED: { className: "bg-sky-600 text-white hover:bg-sky-600" },
  DECLINED: { variant: "outline" },
  RESCINDED: { variant: "destructive" },
};

export function WorkspaceStatusBadge({ status }: { status: WorkspaceStatus }) {
  const style = STATUS_STYLE[status] ?? { variant: "outline" as const };
  const label = WORKSPACE_STATUS_LABEL[status] ?? status;
  return (
    <Badge variant={style.variant} className={style.className}>
      {label}
    </Badge>
  );
}
