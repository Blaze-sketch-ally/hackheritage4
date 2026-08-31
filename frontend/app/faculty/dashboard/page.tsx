import { redirect } from "next/navigation";
import { FacultyDashboardView } from "@/components/faculty/faculty-dashboard-view";
import { createClient } from "@/lib/supabase/server";
import { fetchProfile } from "@/lib/profile";

export default async function FacultyDashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The faculty layout already guarantees an authenticated FACULTY user
  // reaches this point — this is a defensive fallback, not a second check.
  if (!user) redirect("/login");

  const profile = await fetchProfile(supabase, user.id);
  const displayName = profile?.full_name || profile?.username || "Professor";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Welcome back, {displayName} 👋</h1>
        <p className="text-sm text-muted-foreground">
          Track your question bank, review queue, and assessment blueprints.
        </p>
      </div>
      <FacultyDashboardView facultyId={user.id} />
    </div>
  );
}
