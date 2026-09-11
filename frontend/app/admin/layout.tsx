import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getPostLoginRedirectPath } from "@/lib/auth";
import { fetchProfile } from "@/lib/profile";

// proxy.ts already blocks unauthenticated requests to /admin/*, but only
// checks "is there a session" (see docs/PROJECT_CONTEXT.md §9). This layout
// adds the missing role check server-side: only role === "ADMIN" may see
// anything under /admin/*. A signed-in STUDENT/FACULTY/INDUSTRY/INSTITUTION
// user is redirected to their own dashboard, not shown a client-side gate.
// Mirrors app/faculty/layout.tsx -- no shell/sidebar here since the admin
// pages are still "Coming Soon" stubs, just the auth/role gate this route
// group was previously missing entirely.
export default async function AdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
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
