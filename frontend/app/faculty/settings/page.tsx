import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function FacultySettingsPage() {
  return (
    <FeatureRoadmapStub
      title="Faculty Profile & Preference Settings"
      role="Faculty"
      badge="Roadmap · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="settings"
      description="Manage your academic credentials, advisory capacity limits, evaluation notification preferences, and department affiliations."
      highlights={[
        "Advisory intake limits and student research supervision quotas",
        "Assessment authoring and evaluation workspace notification alerts",
        "Public researcher profile visibility and publication link management",
        "Two-factor authentication and secure academic institution SSO linking",
      ]}
      backHref="/faculty/dashboard"
      backLabel="Back to Dashboard"
    />
  );
}
