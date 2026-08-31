import { redirect } from "next/navigation";
import { SkillGapView } from "@/components/student/skill-gap/skill-gap-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentSkillGapPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  return (
    <div className="mx-auto max-w-6xl">
      <SkillGapView />
    </div>
  );
}
