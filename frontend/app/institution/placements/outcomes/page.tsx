import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function InstitutionPlacementsOutcomesPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Placement Outcomes & Audit Registry"
        role="Institution"
        badge="Institution Roadmap"
        description="Verified database of campus placement offers, highest and median compensation tiers, multi-offer reconciliation, and verified offer letter uploads."
        highlights={[
          "Tamper-proof offer letter verification and dual-acceptance prevention",
          "Cohort placement distribution: Tier-1, Super Dream, and Dream offers",
          "NIRF data export templates with 1-click audit documentation",
          "Longitudinal career trajectory tracking for alumni cohorts",
        ]}
        backHref="/institution/dashboard"
        backLabel="Back to Institution Dashboard"
        estimatedRelease="Q4 2026"
        iconName="trophy"
      />
    </div>
  );
}
