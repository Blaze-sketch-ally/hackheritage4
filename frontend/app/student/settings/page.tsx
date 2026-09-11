import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function StudentSettingsPage() {
  return (
    <FeatureRoadmapStub
      title="Student Account & Security Settings"
      role="Student"
      badge="Roadmap · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="settings"
      description="Configure your portal experience, multi-factor authentication, email alert preferences, and privacy controls."
      highlights={[
        "Granular notification preferences for application updates and interview invites",
        "Two-factor authentication (2FA) and active session management",
        "Privacy controls for recruiter profile discovery and contact permissions",
        "Data export (JSON / PDF) for verified skills and assessment transcripts",
      ]}
      backHref="/student/dashboard"
      backLabel="Back to Dashboard"
    />
  );
}
