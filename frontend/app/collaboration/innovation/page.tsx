import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function CollaborationInnovationPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Innovation & Incubation Lab"
        badge="Roadmap Phase 4"
        description="A collaborative sandbox for turning student research and patent ideas into commercial startups with seed funding, incubation support, and corporate sponsorship."
        highlights={[
          "Idea pitching pipelines with multi-tier faculty and VC reviews",
          "Institutional patent filing assistance and IP protection frameworks",
          "Prototyping grants and corporate sponsorship disbursements",
          "Annual demo day showcases with institutional investor networks",
        ]}
        backHref="/collaboration"
        backLabel="Back to Collaboration Hub"
        estimatedRelease="Q1 2027"
        iconName="lightbulb"
      />
    </div>
  );
}
