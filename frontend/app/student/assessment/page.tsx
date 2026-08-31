import { redirect } from "next/navigation";
import Link from "next/link";
import { History } from "lucide-react";
import { AssessmentListView } from "@/components/student/assessment/assessment-list-view";
import { Button } from "@/components/ui/button";
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
      <div className="flex items-start justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Assessments</h1>
          <p className="text-sm text-muted-foreground">
            Take a skill assessment to verify your proficiency.
          </p>
        </div>
        <Button variant="outline" size="sm" render={<Link href="/student/assessment/history" />} nativeButton={false}>
          <History className="size-3.5" /> History
        </Button>
      </div>
      <AssessmentListView />
    </div>
  );
}
