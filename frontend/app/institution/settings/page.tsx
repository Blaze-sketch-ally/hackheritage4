import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function InstitutionSettingsPage() {
  return (
    <FeatureRoadmapStub
      title="Institutional Governance & System Settings"
      role="Institution"
      badge="Roadmap · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="settings"
      description="Configure campus accreditation standards, placement drive protocols, department census sync, and institutional verification authorities."
      highlights={[
        "Campus SIS / ERP student roster synchronization (CSV / API)",
        "NBA / NAAC accreditation outcome parameters and threshold benchmarks",
        "Placement cell drive approval workflow and recruiter qualification criteria",
        "Institutional domain verification and administrative user permissions",
      ]}
      backHref="/institution/dashboard"
      backLabel="Back to Dashboard"
    />
  );
}
