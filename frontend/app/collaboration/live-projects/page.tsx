import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function CollaborationLiveProjectsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Industry Live Projects"
        badge="Roadmap Phase 4"
        description="Real-world engineering and product challenges offered by corporate partners, enabling students to gain tangible production experience under faculty mentorship."
        highlights={[
          "Direct corporate project briefs with verified deliverables",
          "Milestone-based sprint submissions and automated code reviews",
          "Faculty oversight & institutional credit accreditation",
          "Fast-track pre-placement interview consideration for top performers",
        ]}
        backHref="/collaboration"
        backLabel="Back to Collaboration Hub"
        estimatedRelease="Q4 2026"
        iconName="briefcase"
      />
    </div>
  );
}
