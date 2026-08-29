import { redirect } from "next/navigation";
import { StudentShell } from "@/components/student/student-shell";
import { createClient } from "@/lib/supabase/server";
import { getPostLoginRedirectPath } from "@/lib/auth";
import { fetchProfile } from "@/lib/profile";

// proxy.ts already blocks unauthenticated requests to /student/*, but only
// checks "is there a session" (see docs/PROJECT_CONTEXT.md §9). This layout
// adds the missing role check server-side: only role === "STUDENT" may see
// anything under /student/*. A signed-in FACULTY/INDUSTRY/INSTITUTION/ADMIN
// user is redirected to their own dashboard, not shown a client-side gate.
export default async function StudentLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const profile = await fetchProfile(supabase, user.id);

  if (!profile || !profile.role) redirect("/onboarding");
  if (profile.role !== "STUDENT") redirect(getPostLoginRedirectPath(profile.role));

  return <StudentShell profile={profile}>{children}</StudentShell>;
}
