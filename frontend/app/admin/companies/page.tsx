import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function AdminCompaniesPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Corporate Partner Governance"
        role="Admin"
        badge="Admin Roadmap"
        description="Manage corporate registrations, employer vetting, job posting quotas, and partnership agreements across the SkillBridge portal."
        highlights={[
          "Employer verification pipeline with corporate tax ID validation",
          "Recruiter seat management, authorization tiers, and audit logs",
          "Job and internship compliance review queue",
          "Corporate engagement and placement outcome reporting",
        ]}
        backHref="/admin"
        backLabel="Back to Admin Console"
        estimatedRelease="Q4 2026"
        iconName="building"
      />
    </div>
  );
}
