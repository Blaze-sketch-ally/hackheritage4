import { redirect } from "next/navigation";
import { FacultyShell } from "@/components/faculty/faculty-shell";
import { createClient } from "@/lib/supabase/server";
import { getPostLoginRedirectPath } from "@/lib/auth";
import { fetchProfile } from "@/lib/profile";

// Mirrors app/student/layout.tsx's own gate exactly (see that file's
// comment on proxy.ts only checking session presence, not role) -- added
// as part of Phase 1K, since this layout now guards real content
// (question bank / review / blueprint UI) instead of only placeholder
// pages. Only role === "FACULTY" may see anything under /faculty/*; a
// signed-in STUDENT/INDUSTRY/INSTITUTION/ADMIN user is redirected to
// their own dashboard, not shown a client-side gate.
export default async function FacultyLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const profile = await fetchProfile(supabase, user.id);

  if (!profile || !profile.role) redirect("/onboarding");
  if (profile.role !== "FACULTY") redirect(getPostLoginRedirectPath(profile.role));

  return <FacultyShell profile={profile}>{children}</FacultyShell>;
}
