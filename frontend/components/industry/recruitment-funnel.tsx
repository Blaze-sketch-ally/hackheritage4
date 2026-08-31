import { ApplicationTracker } from "@/components/dashboard/application-tracker";
import type { PipelineStage } from "@/lib/mock/industry-dashboard";

/** Reuses ApplicationTracker's exact {label, count}[] bar-funnel
 * rendering -- the same shape a student's application stages and an
 * industry hiring pipeline both are, just labeled differently. Avoids a
 * second, duplicate implementation of the same funnel visualization. */
export function RecruitmentFunnel({ stages }: { stages: PipelineStage[] }) {
  return <ApplicationTracker stages={stages} title="Hiring Pipeline" />;
}
