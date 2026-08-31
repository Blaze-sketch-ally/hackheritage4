import { redirect } from "next/navigation";
import { IndustryShell } from "@/components/industry/industry-shell";
import { createClient } from "@/lib/supabase/server";
import { getPostLoginRedirectPath } from "@/lib/auth";
import { fetchProfile } from "@/lib/profile";

// Mirrors app/student/layout.tsx and app/faculty/layout.tsx exactly --
// proxy.ts only checks session presence, not role (see
// docs/PROJECT_CONTEXT.md §9), so this layout adds the missing role
// check server-side. Previously this layout had NO auth/role check at
// all (a real gap, since it now guards real dashboard content instead of
// only placeholder pages) -- only role === "INDUSTRY" may see anything
// under /industry/*.
export default async function IndustryLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const profile = await fetchProfile(supabase, user.id);

  if (!profile || !profile.role) redirect("/onboarding");
  if (profile.role !== "INDUSTRY") redirect(getPostLoginRedirectPath(profile.role));

  return <IndustryShell profile={profile}>{children}</IndustryShell>;
}
