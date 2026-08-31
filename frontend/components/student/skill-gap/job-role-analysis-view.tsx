import { ReadinessSummary } from "@/components/student/skill-gap/readiness-summary";
import { SkillGapList } from "@/components/student/skill-gap/skill-gap-list";
import { RecommendationsPanel } from "@/components/student/skill-gap/recommendations-panel";
import type { SkillGapJobRoleAnalysis } from "@/types/skill-gap";

/** The full analysis view once a target role is set. Every number/status
 * comes directly from the backend response -- nothing here recalculates
 * readiness, gap, or priority. */
export function JobRoleAnalysisView({ analysis }: { analysis: SkillGapJobRoleAnalysis }) {
  return (
    <div className="space-y-6">
      <ReadinessSummary readinessPercentage={analysis.readiness_percentage} summary={analysis.summary} />

      <div className="space-y-2">
        <h2 className="text-base font-semibold">Skill Gap</h2>
        <SkillGapList skills={analysis.skills} />
      </div>

      <div className="space-y-2">
        <h2 className="text-base font-semibold">Recommended Skills</h2>
        <RecommendationsPanel recommendations={analysis.recommendations} />
      </div>
    </div>
  );
}
