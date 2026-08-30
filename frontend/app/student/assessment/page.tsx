import { redirect } from "next/navigation";
import { AssessmentListView } from "@/components/student/assessment/assessment-list-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentAssessmentPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Assessments</h1>
        <p className="text-sm text-muted-foreground">
          Take a skill assessment to verify your proficiency.
        </p>
      </div>
      <AssessmentListView />
    </div>
  );
}
