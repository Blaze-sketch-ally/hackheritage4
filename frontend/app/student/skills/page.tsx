import { redirect } from "next/navigation";
import { StudentSkillsView } from "@/components/student/skills/student-skills-view";
import { createClient } from "@/lib/supabase/server";
import { fetchActiveSkills, fetchSkillCategories, fetchStudentSkills } from "@/lib/student/skills";

export default async function StudentSkillsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this redirect is just a defensive fallback, not a second
  // role check.
  if (!user) redirect("/login");

  const [catalogSkills, categories, studentSkills] = await Promise.all([
    fetchActiveSkills(supabase),
    fetchSkillCategories(supabase),
    fetchStudentSkills(supabase, user.id),
  ]);

  return (
    <StudentSkillsView
      studentId={user.id}
      initialStudentSkills={studentSkills}
      catalogSkills={catalogSkills}
      categories={categories}
    />
  );
}
