import { redirect } from "next/navigation";
import { ClipboardCheck } from "lucide-react";
import { AssessmentCard } from "@/components/student/assessment-card";
import { EmptyState } from "@/components/common/empty-state";
import { createClient } from "@/lib/supabase/server";
import { fetchActiveAssessments } from "@/lib/student/assessments";

export default async function StudentAssessmentsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this redirect is just a defensive fallback, not a second
  // role check.
  if (!user) redirect("/login");

  const assessments = await fetchActiveAssessments(supabase);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Assessments</h1>
          <p className="text-sm text-muted-foreground">Test your skills and track your progress.</p>
        </div>
      </div>

      {assessments.length === 0 ? (
        <EmptyState icon={ClipboardCheck} title="No assessments available yet." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {assessments.map((assessment) => (
            <AssessmentCard key={assessment.id} assessment={assessment} />
          ))}
        </div>
      )}
    </div>
  );
}
