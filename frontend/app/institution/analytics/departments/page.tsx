import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function InstitutionAnalyticsDepartmentsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Departmental Performance Analytics"
        role="Institution"
        badge="Institution Roadmap"
        description="Granular breakdown of departmental placement percentages, assessment completion rates, internship participation, and faculty publications."
        highlights={[
          "Branch-by-branch placement velocity and median compensation tracking",
          "Student attendance, assessment participation, and backlog correlation",
          "Faculty research output, patents, and consultancy revenue tracking",
          "Automated annual departmental appraisal dossier generation",
        ]}
        backHref="/institution/dashboard"
        backLabel="Back to Institution Dashboard"
        estimatedRelease="Q4 2026"
        iconName="trending-up"
      />
    </div>
  );
}
