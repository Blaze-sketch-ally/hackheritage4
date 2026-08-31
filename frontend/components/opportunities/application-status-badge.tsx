import { Badge } from "@/components/ui/badge";
import type { ApplicationStatus } from "@/types/application";

const STATUS_STYLE: Record<ApplicationStatus, { label: string; className?: string; variant?: "outline" | "destructive" | "secondary" }> = {
  APPLIED: { label: "Applied", variant: "secondary" },
  SHORTLISTED: { label: "Shortlisted", className: "bg-indigo-600 text-white hover:bg-indigo-600" },
  INTERVIEW: { label: "Interview", className: "bg-amber-500 text-white hover:bg-amber-500" },
  SELECTED: { label: "Selected", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
  REJECTED: { label: "Rejected", variant: "destructive" },
};

/** Shared by the student ApplicationTable and the industry ApplicantTable
 * -- one status vocabulary, rendered identically on both sides. */
export function ApplicationStatusBadge({ status }: { status: ApplicationStatus }) {
  const style = STATUS_STYLE[status];
  return (
    <Badge variant={style.variant} className={style.className}>
      {style.label}
    </Badge>
  );
}
