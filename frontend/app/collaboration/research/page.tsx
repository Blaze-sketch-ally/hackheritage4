import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function CollaborationResearchPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Joint Research & Publications"
        badge="Roadmap Phase 4"
        description="Foster collaborative research between university departments, doctoral scholars, and corporate R&D divisions with peer-reviewed publication workflows."
        highlights={[
          "Corporate-sponsored R&D grant discovery and application workflow",
          "Co-authorship collaboration workspaces with versioned drafts",
          "IRB & ethics compliance checklist automation",
          "Citation tracking and institutional research impact analytics",
        ]}
        backHref="/collaboration"
        backLabel="Back to Collaboration Hub"
        estimatedRelease="Q1 2027"
        iconName="research"
      />
    </div>
  );
}
