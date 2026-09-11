import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function IndustryMentorshipPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Executive & Engineer Mentorship Program"
        role="Industry"
        badge="Industry Roadmap"
        description="Empower your senior engineering and product leaders to mentor high-potential students, conduct technical mock interviews, and build early talent pipelines."
        highlights={[
          "Mentor roster management with availability and domain expertise matching",
          "Calendar synchronisation for 1-on-1 virtual advisory sessions",
          "Structured mentorship rubrics and candidate feedback scorecards",
          "Direct fast-track recommendation workflow into active hiring pipelines",
        ]}
        backHref="/industry/dashboard"
        backLabel="Back to Industry Dashboard"
        estimatedRelease="Q4 2026"
        iconName="users"
      />
    </div>
  );
}
