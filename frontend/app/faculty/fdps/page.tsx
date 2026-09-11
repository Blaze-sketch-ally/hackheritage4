import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function FacultyFdpsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Faculty Development Programs (FDP)"
        role="Faculty"
        badge="Faculty Roadmap"
        description="Participate in certified Faculty Development Programs hosted by premier institutions and global technology companies to upskill in emerging tech."
        highlights={[
          "AICTE & UGC-accredited professional development training catalogs",
          "Direct sponsorship and institutional leave approval integration",
          "Interactive pedagogical workshops on AI, quantum, and modern software architectures",
          "Automated credit accrual and verifiable digital certificate issuance",
        ]}
        backHref="/faculty/dashboard"
        backLabel="Back to Faculty Dashboard"
        estimatedRelease="Q4 2026"
        iconName="graduation-cap"
      />
    </div>
  );
}
