import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function FacultyWorkshopsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Faculty-Led Masterclasses & Workshops"
        role="Faculty"
        badge="Faculty Roadmap"
        description="Propose, coordinate, and host inter-collegiate technical workshops, hands-on lab sessions, and research bootcamps."
        highlights={[
          "Workshop proposal pipeline with departmental budget approvals",
          "Automated student registration, waitlist, and attendance management",
          "Live virtual classroom and GPU-accelerated lab environment provisioning",
          "Post-workshop outcome analysis and student feedback dashboards",
        ]}
        backHref="/faculty/dashboard"
        backLabel="Back to Faculty Dashboard"
        estimatedRelease="Q4 2026"
        iconName="sparkles"
      />
    </div>
  );
}
