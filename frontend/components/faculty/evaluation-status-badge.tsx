import { Badge } from "@/components/ui/badge";
import type { EvaluationStatus } from "@/types/evaluation";

const LABELS: Record<EvaluationStatus, string> = {
  ASSIGNED: "Pending",
  IN_PROGRESS: "In Progress",
  SUBMITTED: "Submitted",
  FINALIZED: "Finalized",
};

/** Never rely on color alone -- the label text itself always names the
 * real backend status (via LABELS), never an icon/color-only signal. */
export function EvaluationStatusBadge({ status }: { status: EvaluationStatus }) {
  switch (status) {
    case "ASSIGNED":
      return <Badge variant="outline">{LABELS.ASSIGNED}</Badge>;
    case "IN_PROGRESS":
      return <Badge className="bg-amber-600 text-white hover:bg-amber-600/90 dark:bg-amber-500">{LABELS.IN_PROGRESS}</Badge>;
    case "SUBMITTED":
      return <Badge className="bg-indigo-600 text-white hover:bg-indigo-600/90 dark:bg-indigo-500">{LABELS.SUBMITTED}</Badge>;
    case "FINALIZED":
      return <Badge className="bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500">{LABELS.FINALIZED}</Badge>;
  }
}
