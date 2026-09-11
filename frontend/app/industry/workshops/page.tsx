import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function IndustryWorkshopsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Corporate Masterclasses & Workshops"
        role="Industry"
        badge="Industry Roadmap"
        description="Sponsor and host specialized technical workshops, code labs, and hackathons across partner campuses to build brand equity and discover top student talent."
        highlights={[
          "Targeted campus outreach based on department skill profiles",
          "Integrated webinar, code repository, and live evaluation links",
          "Automated candidate attendee talent scoring and fast-track interviews",
          "Branded digital certificate generation with verifiable corporate badges",
        ]}
        backHref="/industry/dashboard"
        backLabel="Back to Industry Dashboard"
        estimatedRelease="Q4 2026"
        iconName="sparkles"
      />
    </div>
  );
}
