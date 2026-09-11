import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function CollaborationMentorshipPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <FeatureRoadmapStub
        title="Cross-Industry Mentorship"
        badge="Roadmap Phase 4"
        description="Connect students with vetted industry professionals and faculty advisors for structured 1-on-1 mentorship cycles, mock interviews, and career pathway coaching."
        highlights={[
          "Automated mentor-mentee matching based on career trajectories",
          "Integrated session scheduling with calendar synchronisation",
          "Goal-oriented milestone tracking and verified progress sign-offs",
          "Verifiable mentorship completion credentials added to student profile",
        ]}
        backHref="/collaboration"
        backLabel="Back to Collaboration Hub"
        estimatedRelease="Q4 2026"
        iconName="users"
      />
    </div>
  );
}
