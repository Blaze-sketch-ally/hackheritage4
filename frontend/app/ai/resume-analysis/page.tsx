import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function AiResumeAnalysisPage() {
  return (
    <FeatureRoadmapStub
      title="AI Resume & Profile Analyzer"
      role="Student"
      badge="AI Intelligence · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="file-text"
      description="Automated ATS scoring, keyword alignment, and deep semantic evaluation of student resumes against live industry job and internship descriptions."
      highlights={[
        "ATS keyword density scoring and recruiter parsing preview",
        "Actionable bullet-point phrasing improvements and impact metric suggestions",
        "Direct alignment score against specific published job openings",
        "One-click embedding of verified skill badges and portfolio projects",
      ]}
      backHref="/student/dashboard"
      backLabel="Back to Dashboard"
    />
  );
}
