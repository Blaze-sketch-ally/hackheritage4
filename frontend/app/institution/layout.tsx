import { redirect } from "next/navigation";
import { InstitutionShell } from "@/components/institution/institution-shell";
import { createClient } from "@/lib/supabase/server";
import { getPostLoginRedirectPath } from "@/lib/auth";
import { fetchProfile } from "@/lib/profile";

// proxy.ts already blocks unauthenticated requests to /institution/*, but
// only checks "is there a session" (see docs/PROJECT_CONTEXT.md §9). This
// layout adds the missing role check server-side: only role === "INSTITUTION"
// may see anything under /institution/*. A signed-in STUDENT/FACULTY/
// INDUSTRY/ADMIN user is redirected to their own dashboard, not shown a
// client-side gate. Mirrors app/student/layout.tsx and app/industry/layout.tsx,
// including the authenticated shell (sidebar + header) -- the header is what
// exposes the Sign out action, matching how Student/Industry expose logout.
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

  return <InstitutionShell profile={profile}>{children}</InstitutionShell>;
}
