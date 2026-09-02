import { redirect } from "next/navigation";
import { CareerView } from "@/components/student/career/career-view";
import { createClient } from "@/lib/supabase/server";
import { fetchStudentProfile } from "@/lib/student/profile";

export default async function StudentCareerPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  const studentProfile = await fetchStudentProfile(supabase, user.id);

  return <CareerView careerGoals={studentProfile?.career_goals ?? null} />;
}
