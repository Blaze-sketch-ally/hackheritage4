import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function AdminSettingsPage() {
  return (
    <FeatureRoadmapStub
      title="Global Platform Configuration & Security"
      role="Admin"
      badge="System Architecture · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="settings"
      description="System-wide runtime feature flags, authentication provider controls, rate-limiting rules, maintenance mode, and security audit configurations."
      highlights={[
        "Global feature flags and staged canary deployment switches",
        "Supabase Auth & SAML/SSO enterprise directory connectors",
        "API rate limiting and DDoS perimeter defense thresholds",
        "Automated backup scheduling and cross-region replication health",
      ]}
      backHref="/admin/dashboard"
      backLabel="Back to Admin Console"
    />
  );
}
