import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { AssessmentHistoryView } from "@/components/student/assessment/assessment-history-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentAssessmentHistoryPage() {
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
        <Link
          href="/student/assessment"
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> All assessments
        </Link>
        <h1 className="mt-2 text-xl font-semibold">Assessment History</h1>
        <p className="text-sm text-muted-foreground">Every assessment attempt you&apos;ve made, most recent first.</p>
      </div>
      <AssessmentHistoryView />
    </div>
  );
}
