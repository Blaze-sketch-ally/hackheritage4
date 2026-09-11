import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function IndustryAnalyticsPage() {
  return (
    <FeatureRoadmapStub
      title="Recruitment & Talent Analytics"
      role="Industry"
      badge="Analytics · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="bar-chart"
      description="Deep analytical insights into your hiring funnel velocity, applicant qualification rates, assessment scores, and university talent distribution."
      highlights={[
        "Full-funnel conversion metrics from application to hire",
        "Skill proficiency distribution across applicant cohorts",
        "Institution-wise candidate performance and yield comparison",
        "Exportable compliance & affirmative hiring reports",
      ]}
      backHref="/industry/dashboard"
      backLabel="Back to Dashboard"
    />
  );
}
