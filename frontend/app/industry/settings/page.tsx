import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function IndustrySettingsPage() {
  return (
    <FeatureRoadmapStub
      title="Company & Recruiter Settings"
      role="Industry"
      badge="Roadmap · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="settings"
      description="Manage your enterprise recruiting team members, brand assets, notification rules, and API integrations with corporate HRIS / ATS systems."
      highlights={[
        "Team seat allocation and role-based recruiter permissions",
        "Webhook endpoints & API keys for Workday / Greenhouse synchronization",
        "Company branding assets, verified domain authentication, and logo management",
        "Automated candidate rejection & interview invitation email templates",
      ]}
      backHref="/industry/dashboard"
      backLabel="Back to Dashboard"
    />
  );
}
