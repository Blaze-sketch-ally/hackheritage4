import { Badge } from "@/components/ui/badge";
import type { ProgramStatus } from "@/types/internship-program";

const STYLE: Record<ProgramStatus, { className?: string; variant?: "outline" | "secondary" }> = {
  DRAFT: { variant: "secondary" },
  PUBLISHED: { className: "bg-emerald-600 text-white hover:bg-emerald-600" },
  ARCHIVED: { variant: "outline" },
};

const LABEL: Record<ProgramStatus, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  ARCHIVED: "Archived",
};

export function ProgramStatusBadge({ status }: { status: ProgramStatus }) {
  const s = STYLE[status] ?? { variant: "outline" as const };
  return (
    <Badge variant={s.variant} className={s.className}>
      {LABEL[status] ?? status}
    </Badge>
  );
}
