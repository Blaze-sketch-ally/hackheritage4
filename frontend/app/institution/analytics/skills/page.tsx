import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function InstitutionAnalyticsSkillsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Campus Skill Gap Intelligence"
        role="Institution"
        badge="Institution Roadmap"
        description="Analyze student cohort proficiency across modern technology stacks and benchmark campus readiness against current industry recruitment trends."
        highlights={[
          "Comparative skill gap heatmaps across semesters and branches",
          "Real-time calibration against live hiring requirements in the AIC network",
          "Curriculum enhancement recommendations backed by data",
          "Exportable compliance summaries for NAAC & NBA accreditation criteria",
        ]}
        backHref="/institution/dashboard"
        backLabel="Back to Institution Dashboard"
        estimatedRelease="Q4 2026"
        iconName="bar-chart"
      />
    </div>
  );
}
