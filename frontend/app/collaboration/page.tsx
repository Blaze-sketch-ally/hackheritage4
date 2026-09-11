import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function CollaborationPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Collaboration Hub"
        badge="Roadmap Phase 4"
        description="A unified platform connecting academia and industry for applied research, joint innovation projects, corporate-sponsored hackathons, and cross-institutional student exchanges."
        highlights={[
          "Inter-institutional project discovery & cross-campus team matching",
          "Industry-sponsored problem statements and capstone initiatives",
          "Shared IP frameworks, legal agreements, and NDA management",
          "Joint funding tracking & grant milestone verification",
        ]}
        backHref="/"
        backLabel="Back to Home"
        estimatedRelease="Q4 2026"
        iconName="layers"
      />
    </div>
  );
}
