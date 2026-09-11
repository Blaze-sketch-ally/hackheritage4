import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function OpportunitiesCoursesPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Accredited Courses & Modules"
        badge="Roadmap Phase 4"
        description="Discover industry-certified training modules and university courses designed to bridge theoretical knowledge and enterprise engineering standards."
        highlights={[
          "Industry-aligned curriculum created with corporate technology leaders",
          "Self-paced interactive coding sandboxes and graded assessments",
          "Institutional credit transfer and autonomous transcript updates",
          "Digital verifiable credential issued upon course completion",
        ]}
        backHref="/"
        backLabel="Back to Home"
        estimatedRelease="Q4 2026"
        iconName="graduation-cap"
      />
    </div>
  );
}
