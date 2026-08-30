import { redirect } from "next/navigation";
import { TakeAssessmentView } from "@/components/student/assessments/take-assessment-view";
import { createClient } from "@/lib/supabase/server";
import {
  fetchAssessmentById,
  fetchAssessmentQuestions,
  fetchMyAnswers,
  findInProgressAttempt,
} from "@/lib/student/assessments";

export default async function TakeAssessmentPage({
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
  if (!assessment) redirect("/student/assessments");

  // Starting an attempt only happens from the details page's "Start
  // Assessment" button — visiting /take directly without one sends the
  // student back there rather than silently creating an attempt as a
  // side effect of a page load.
  const attempt = await findInProgressAttempt(supabase, user.id, assessmentId);
  if (!attempt) redirect(`/student/assessments/${assessmentId}`);

  const [questions, answers] = await Promise.all([
    fetchAssessmentQuestions(supabase, assessmentId),
    fetchMyAnswers(supabase, attempt.id),
  ]);

  return <TakeAssessmentView assessment={assessment} attempt={attempt} questions={questions} initialAnswers={answers} />;
}
