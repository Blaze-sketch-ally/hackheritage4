import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function IndustryProjectsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Industry Project Briefs & Sponsoring"
        role="Industry"
        badge="Industry Roadmap"
        description="Post engineering problem statements, sponsor academic capstones, and collaborate directly with top undergraduate and graduate research teams."
        highlights={[
          "Problem statement submission with IP ownership and confidentiality controls",
          "Student team proposal review and milestone approval pipeline",
          "Direct messaging with faculty principal investigators and student leads",
          "Code review integration with GitHub / GitLab enterprise repositories",
        ]}
        backHref="/industry/dashboard"
        backLabel="Back to Industry Dashboard"
        estimatedRelease="Q4 2026"
        iconName="layers"
      />
    </div>
  );
}
