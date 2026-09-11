import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function AdminInstitutionsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Partner Institutions Management"
        role="Admin"
        badge="Admin Roadmap"
        description="Onboard universities, manage institutional MoUs, configure departmental structures, and oversee institutional administrator access."
        highlights={[
          "University onboarding portal with NIRF / NAAC accreditation tracking",
          "Department, faculty roster, and cohort hierarchy configuration",
          "SSO integration setup and campus domain verification",
          "Benchmarking metrics comparing placements and skill benchmarks across institutes",
        ]}
        backHref="/admin"
        backLabel="Back to Admin Console"
        estimatedRelease="Q4 2026"
        iconName="building"
      />
    </div>
  );
}
