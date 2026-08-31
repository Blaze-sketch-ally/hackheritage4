import { redirect } from "next/navigation";
import { IndustryShell } from "@/components/industry/industry-shell";
import { createClient } from "@/lib/supabase/server";
import { getPostLoginRedirectPath } from "@/lib/auth";
import { fetchProfile } from "@/lib/profile";

// proxy.ts already blocks unauthenticated requests to /industry/*, but only
// checks "is there a session" (see docs/PROJECT_CONTEXT.md §9). This layout
// adds the missing role check server-side: only role === "INDUSTRY" may see
// anything under /industry/*. A signed-in STUDENT/FACULTY/INSTITUTION/ADMIN
// user is redirected to their own dashboard, not shown a client-side gate.
// Mirrors app/student/layout.tsx exactly.
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
