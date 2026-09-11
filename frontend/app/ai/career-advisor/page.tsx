import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function AiCareerAdvisorPage() {
  return (
    <FeatureRoadmapStub
      title="AI Career Advisor"
      role="Student"
      badge="AI Intelligence · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="sparkles"
      description="Interactive conversational AI guidance designed to synthesize your academic coursework, verified skill assessments, and career ambitions into personalized growth strategies."
      highlights={[
        "Context-aware advisory grounded in your objective skill assessment scores",
        "Role-specific interview preparation and technical practice questions",
        "Explainable matching insights detailing why specific companies fit your profile",
        "Personalized milestone roadmap to qualify for Tier-1 corporate placements",
      ]}
      backHref="/student/dashboard"
      backLabel="Back to Dashboard"
    />
  );
}
