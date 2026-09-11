import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function OpportunitiesProjectsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Open Project Directory"
        badge="Roadmap Phase 4"
        description="Browse open-source contributions, institutional research projects, and corporate challenges open to student applications."
        highlights={[
          "Filter by technology stack, difficulty level, and domain",
          "Team formation tools to recruit co-contributors across universities",
          "Mentor pairing with experienced engineers and academic faculty",
          "Showcase featured capstones directly on student public portfolios",
        ]}
        backHref="/"
        backLabel="Back to Home"
        estimatedRelease="Q4 2026"
        iconName="layers"
      />
    </div>
  );
}
