import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function IndustryShortlistedPage() {
  return (
    <FeatureRoadmapStub
      title="Shortlisted Candidate Management"
      role="Industry"
      badge="Active Pipeline"
      estimatedRelease="Available in ATS"
      iconName="trophy"
      description="Review candidates who have successfully passed your initial review and technical screening. You can schedule interviews, send offers, and collaborate with your hiring team."
      highlights={[
        "Multi-reviewer scorecard evaluation and interviewer notes",
        "Direct interview scheduling with candidate notification",
        "Offer letter generation and digital acceptance tracking",
        "Candidate comparative side-by-side skill benchmark view",
      ]}
      backHref="/industry/applicants?status=SHORTLISTED"
      backLabel="View Shortlisted in Applicants ATS"
    />
  );
}
