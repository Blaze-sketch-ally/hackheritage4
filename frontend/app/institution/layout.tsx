import { redirect } from "next/navigation";
import { InstitutionShell } from "@/components/institution/institution-shell";
import { createClient } from "@/lib/supabase/server";
import { getPostLoginRedirectPath } from "@/lib/auth";
import { fetchProfile } from "@/lib/profile";

// Mirrors app/student/layout.tsx, app/faculty/layout.tsx, and
// app/industry/layout.tsx exactly -- proxy.ts only checks session
// presence, not role (see docs/PROJECT_CONTEXT.md §9), so this layout
// adds the missing role check server-side. Previously this layout had NO
// auth/role check at all -- only role === "INSTITUTION" may see anything
// under /institution/*.
export default async function InstitutionLayout({ children }: { children: React.ReactNode }) {
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
