import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function AdminStudentsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Student Registry & Records"
        role="Admin"
        badge="Admin Roadmap"
        description="Supervise enrolled students across all partner colleges, oversee profile verification, and manage cross-institutional transcripts."
        highlights={[
          "Global student directory with advanced demographic & performance filtering",
          "Identity and credential verification workflows",
          "Bulk enrollment import via institutional CSV/API integration",
          "Account suspension, dispute management, and data privacy controls",
        ]}
        backHref="/admin"
        backLabel="Back to Admin Console"
        estimatedRelease="Q4 2026"
        iconName="graduation-cap"
      />
    </div>
  );
}
