import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { AssessmentTakingView } from "@/components/student/assessment/assessment-taking-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentAssessmentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Link
        href="/student/assessment"
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> All assessments
      </Link>
      <AssessmentTakingView assessmentId={id} />
    </div>
  );
}
