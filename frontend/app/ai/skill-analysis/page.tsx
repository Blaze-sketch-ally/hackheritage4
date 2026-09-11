import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function AiSkillAnalysisPage() {
  return (
    <FeatureRoadmapStub
      title="AI Skill Gap & Market Intelligence"
      role="Student"
      badge="AI Intelligence · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="trending-up"
      description="Real-time market comparison between your verified competencies and live employer demand across regional and global hiring pipelines."
      highlights={[
        "Live technical skill demand trends from active employer postings",
        "Target role deficit visualization with prioritized closing actions",
        "Predictive career readiness modeling based on completed modules",
        "Automated recommendation of verified tests to validate in-demand skills",
      ]}
      backHref="/student/dashboard"
      backLabel="Back to Dashboard"
    />
  );
}
