import { Badge } from "@/components/ui/badge";
import type { StipendStatus } from "@/types/internship-stipend";

// The four stipend_disbursements.disbursement_status values (migration
// 039). RELEASED / CANCELLED are terminal.
type Style = { className?: string; variant?: "outline" | "destructive" };

const STATUS_STYLE: Record<StipendStatus, Style> = {
  PENDING: { className: "bg-amber-500 text-white hover:bg-amber-500" },
  APPROVED: { className: "bg-indigo-600 text-white hover:bg-indigo-600" },
  RELEASED: { className: "bg-emerald-600 text-white hover:bg-emerald-600" },
  CANCELLED: { variant: "outline" },
};

const STATUS_LABEL: Record<StipendStatus, string> = {
  PENDING: "Pending",
  APPROVED: "Approved",
  RELEASED: "Released",
  CANCELLED: "Cancelled",
};

export function StipendStatusBadge({ status }: { status: StipendStatus }) {
  const style = STATUS_STYLE[status] ?? { variant: "outline" as const };
  return (
    <Badge variant={style.variant} className={style.className}>
      {STATUS_LABEL[status] ?? status}
    </Badge>
  );
}
