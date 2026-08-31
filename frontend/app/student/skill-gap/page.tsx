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
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Skill Gap Analysis</h1>
        <p className="text-sm text-muted-foreground">
          Compare your assessed skills against the requirements of a career role.
        </p>
      </div>
      <SkillGapView />
    </div>
  );
}
