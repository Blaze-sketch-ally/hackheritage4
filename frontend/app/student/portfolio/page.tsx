import { redirect } from "next/navigation";
import { PortfolioView } from "@/components/student/portfolio/portfolio-view";
import { createClient } from "@/lib/supabase/server";
import { fetchProfile } from "@/lib/profile";
import { fetchStudentProfile } from "@/lib/student/profile";

export default async function StudentPortfolioPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  const [profile, studentProfile] = await Promise.all([
    fetchProfile(supabase, user.id),
    fetchStudentProfile(supabase, user.id),
  ]);

  const displayName = profile?.full_name || profile?.username || "My Portfolio";

  return (
    <PortfolioView
      displayName={displayName}
      headline={studentProfile?.career_goals ?? null}
    />
  );
}
