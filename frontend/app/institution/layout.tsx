import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getPostLoginRedirectPath } from "@/lib/auth";
import { fetchProfile } from "@/lib/profile";

// proxy.ts already blocks unauthenticated requests to /institution/*, but
// only checks "is there a session" (see docs/PROJECT_CONTEXT.md §9). This
// layout adds the missing role check server-side: only role === "INSTITUTION"
// may see anything under /institution/*. A signed-in STUDENT/FACULTY/
// INDUSTRY/ADMIN user is redirected to their own dashboard, not shown a
// client-side gate. Mirrors app/student/layout.tsx and app/industry/layout.tsx
// -- deliberately no shell/sidebar here (none exists for Institution yet,
// and Phase 10E's scope doesn't call for building one), just the auth/role
// gate the new /institution/collaborations page needs.
export default async function InstitutionLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const profile = await fetchProfile(supabase, user.id);

  if (!profile || !profile.role) redirect("/onboarding");
  if (profile.role !== "INSTITUTION") redirect(getPostLoginRedirectPath(profile.role));

  return <div className="min-h-screen">{children}</div>;
}
