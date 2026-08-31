import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getPostLoginRedirectPath } from "@/lib/auth";
import { fetchProfile } from "@/lib/profile";

// Mirrors app/student/layout.tsx, app/faculty/layout.tsx,
// app/industry/layout.tsx, and app/institution/layout.tsx exactly --
// proxy.ts only checks session presence, not role (see
// docs/PROJECT_CONTEXT.md §9). This was previously the one role layout
// with NO auth/role check at all, found during a full-project
// architecture audit: any authenticated user of any role could navigate
// directly to /admin/* and render its (currently stub) content. No
// AdminShell/sidebar exists yet -- unlike the other four roles, ADMIN has
// no real dashboard content or navigation to wrap (see the Phase 1L+
// planning roadmap: admin remains explicitly out of scope until a real
// feature is built there) -- this only closes the access gap, it does
// not add a shell. There is also currently no way to provision a real
// ADMIN account through the app at all (002_protect_admin_role.sql), so
// this check can never actually let anyone through today -- it exists
// for when that changes.
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const profile = await fetchProfile(supabase, user.id);

  if (!profile || !profile.role) redirect("/onboarding");
  if (profile.role !== "ADMIN") redirect(getPostLoginRedirectPath(profile.role));

  return <div className="min-h-screen">{children}</div>;
}
