import { redirect } from "next/navigation";
import { AlertCircle } from "lucide-react";
import { AssessmentDetailView } from "@/components/student/assessments/assessment-detail-view";
import { createClient } from "@/lib/supabase/server";
import { fetchAssessmentById, findInProgressAttempt } from "@/lib/student/assessments";

export default async function AssessmentDetailPage({
  params,
}: {
  params: Promise<{ assessmentId: string }>;
}) {
  const { assessmentId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const assessment = await fetchAssessmentById(supabase, assessmentId);

  if (!assessment) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-16 text-center">
        <AlertCircle className="size-8 text-muted-foreground" aria-hidden="true" />
        <div className="space-y-1">
          <p className="text-sm font-medium">This assessment is not available.</p>
          <p className="text-sm text-muted-foreground">
            It may not exist, may be inactive, or you may not have access to it.
          </p>
        </div>
      </div>
    );
  }

  const existingAttempt = await findInProgressAttempt(supabase, user.id, assessmentId);

  return <AssessmentDetailView studentId={user.id} assessment={assessment} existingAttempt={existingAttempt} />;
}
