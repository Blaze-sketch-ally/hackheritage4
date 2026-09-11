import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function IndustrySelectedPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Selected Candidates & Offer Management"
        role="Industry"
        badge="Industry Roadmap"
        description="Manage final candidate selections, generate digital offer letters, track candidate acceptance status, and oversee pre-onboarding documentation."
        highlights={[
          "Automated offer letter generation with customizable institutional templates",
          "Real-time candidate acceptance, decline, and counter-offer tracking",
          "Digital document collection for degree certificates and credentials",
          "Seamless handoff to corporate HRMS and payroll onboarding systems",
        ]}
        backHref="/industry/dashboard"
        backLabel="Back to Industry Dashboard"
        estimatedRelease="Q4 2026"
        iconName="award"
      />
    </div>
  );
}
