import { redirect } from "next/navigation";
import { OpportunityListView } from "@/components/opportunities/opportunity-list-view";
import { createClient } from "@/lib/supabase/server";

// A filtered view over the same unified opportunity system as
// /student/opportunities -- never a second list implementation (see
// OpportunityListView's own docstring).
export default async function StudentJobsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Jobs</h1>
        <p className="text-sm text-muted-foreground">Full-time roles matched against your assessed skills.</p>
      </div>
      <OpportunityListView lockedType="JOB" detailBasePath="/student/jobs" />
    </div>
  );
}
