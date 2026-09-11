import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function OpportunitiesJobsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Public Job Directory"
        badge="Roadmap Phase 4"
        description="Explore verified full-time engineering, research, and technical positions from vetted corporate partners across the SkillBridge network."
        highlights={[
          "Transparent compensation ranges and verified role requirements",
          "Automated skill match score calculated from your verified profile",
          "Direct 1-click application submission with verifiable credentials",
          "Real-time applicant pipeline status tracking and interview alerts",
        ]}
        backHref="/"
        backLabel="Back to Home"
        estimatedRelease="Q4 2026"
        iconName="briefcase"
      />
    </div>
  );
}
