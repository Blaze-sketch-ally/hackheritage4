import { redirect } from "next/navigation";
import { OpportunityListView } from "@/components/student/opportunities/opportunity-list-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentJobsPage() {
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
        <h1 className="text-xl font-semibold">Jobs &amp; Placements</h1>
        <p className="text-sm text-muted-foreground">
          Browse published jobs and see your real skill match for each.
        </p>
      </div>
      <OpportunityListView sourceType="JOB" detailBasePath="/student/jobs" />
    </div>
  );
}
