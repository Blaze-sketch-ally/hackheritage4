import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function StudentCareerPage() {
  return (
    <FeatureRoadmapStub
      title="Career Pathway Navigator"
      role="Student"
      badge="Roadmap · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="compass"
      description="The Career Pathway Navigator dynamically analyzes your verified skills, academic background, and target roles to construct bespoke career roadmaps and industry placement projections."
      highlights={[
        "Target role skill-gap analysis with actionable closing roadmaps",
        "Salary & placement trajectory benchmarking across alumni cohorts",
        "Direct matching with corporate internship pathways and job requirements",
        "Personalized milestone checklist to reach target job readiness",
      ]}
      backHref="/student/dashboard"
      backLabel="Back to Dashboard"
    />
  );
}
