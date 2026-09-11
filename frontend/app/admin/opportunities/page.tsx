import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function AdminOpportunitiesPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Opportunity Moderation Center"
        role="Admin"
        badge="Admin Roadmap"
        description="Monitor, audit, and approve job postings, internship listings, and research projects submitted across the portal."
        highlights={[
          "Automated policy compliance scanner for compensation and terms",
          "Reporting & dispute resolution system for student applicants",
          "Listing lifecycle management (publish, archive, feature, suspend)",
          "Cross-platform analytics on application volumes and placement rates",
        ]}
        backHref="/admin"
        backLabel="Back to Admin Console"
        estimatedRelease="Q4 2026"
        iconName="briefcase"
      />
    </div>
  );
}
