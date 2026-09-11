import { Badge } from "@/components/ui/badge";
import type { JobProgramStatus } from "@/types/job-training-program";

const STYLE: Record<JobProgramStatus, { className?: string; variant?: "outline" | "secondary" }> = {
  DRAFT: { variant: "secondary" },
  PUBLISHED: { className: "bg-emerald-600 text-white hover:bg-emerald-600" },
  ARCHIVED: { variant: "outline" },
};

const LABEL: Record<JobProgramStatus, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  ARCHIVED: "Archived",
};

export function JobProgramStatusBadge({ status }: { status: JobProgramStatus }) {
  const s = STYLE[status] ?? { variant: "outline" as const };
  return (
    <Badge variant={s.variant} className={s.className}>
      {LABEL[status] ?? status}
    </Badge>
  );
}
