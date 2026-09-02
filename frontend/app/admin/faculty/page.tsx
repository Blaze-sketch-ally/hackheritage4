import { FacultyPermissionsView } from "@/components/admin/faculty-permissions-view";

// The /admin/* layout (app/admin/layout.tsx) already guards this page to
// role === "ADMIN" server-side; FacultyPermissionsView is a management
// UI over an already-secured API (require_admin() + each admin_* RPC's
// own is_admin() check), never a second authorization decision.
export default function Page() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-8">
      <div>
        <h1 className="text-xl font-semibold">Faculty assessment permissions</h1>
        <p className="text-sm text-muted-foreground">
          Grant, suspend, or revoke Faculty members&apos; assessment capabilities.
        </p>
      </div>
      <FacultyPermissionsView />
    </div>
  );
}
