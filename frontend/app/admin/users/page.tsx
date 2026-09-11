import { FeatureRoadmapStub } from "@/components/common/feature-roadmap-stub";

export default function AdminUsersPage() {
  return (
    <FeatureRoadmapStub
      title="Platform User & Role Governance"
      role="Admin"
      badge="Identity Management · Q4 2026"
      estimatedRelease="Q4 2026"
      iconName="users"
      description="Centralized administration of student, faculty, recruiter, and institutional accounts with session management and role provisioning."
      highlights={[
        "Multi-tenant directory with role assignment and privilege modification",
        "Administrative password resets and session revocation controls",
        "SSO and academic domain email whitelist configuration",
        "Suspension and security flag review queues",
      ]}
      backHref="/admin/dashboard"
      backLabel="Back to Admin Console"
    />
  );
}
