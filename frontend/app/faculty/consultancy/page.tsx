import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function FacultyConsultancyPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Corporate Consultancy & Advisory"
        role="Faculty"
        badge="Faculty Roadmap"
        description="Connect faculty domain expertise with enterprise R&D, corporate advisory boards, technical audits, and specialized consultancy projects."
        highlights={[
          "Enterprise consultancy opportunity matching based on research specialization",
          "Institutional revenue sharing calculation and automated MoU workflows",
          "Milestone-based deliverable sign-offs and verified project billing",
          "Confidential NDA repository and corporate client communication hub",
        ]}
        backHref="/faculty/dashboard"
        backLabel="Back to Faculty Dashboard"
        estimatedRelease="Q4 2026"
        iconName="briefcase"
      />
    </div>
  );
}
