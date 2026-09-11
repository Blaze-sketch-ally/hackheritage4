import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function OpportunitiesInternshipsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Public Internship Board"
        badge="Roadmap Phase 4"
        description="Search structured summer, semester-long, and winter internships offered by accredited startup and corporate employers."
        highlights={[
          "Verified stipend details, work modes (remote/hybrid/onsite), and durations",
          "Integrated university NOC (No Objection Certificate) request workflow",
          "Automated mentorship checkpoints and weekly progress logbooks",
          "Conversion tracking towards full-time Pre-Placement Offers (PPO)",
        ]}
        backHref="/"
        backLabel="Back to Home"
        estimatedRelease="Q4 2026"
        iconName="compass"
      />
    </div>
  );
}
