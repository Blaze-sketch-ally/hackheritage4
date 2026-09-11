import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function InstitutionPlacementsDrivesPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="On-Campus Recruitment Drives"
        role="Institution"
        badge="Institution Roadmap"
        description="Coordinate full-lifecycle placement drives: company shortlisting criteria, test room scheduling, interview rounds, and real-time result publishing."
        highlights={[
          "Recruiter drive registration and eligibility criteria rule configuration",
          "Automated student eligibility filtering by CGPA and active backlogs",
          "Slot allocation for pre-placement talks, online tests, and interviews",
          "Real-time round progression and offer declaration announcements",
        ]}
        backHref="/institution/dashboard"
        backLabel="Back to Institution Dashboard"
        estimatedRelease="Q4 2026"
        iconName="target"
      />
    </div>
  );
}
