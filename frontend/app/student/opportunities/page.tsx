import { redirect } from "next/navigation";
import { OpportunityListView } from "@/components/opportunities/opportunity-list-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentOpportunitiesPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Opportunities</h1>
        <p className="text-sm text-muted-foreground">
          Browse jobs and internships, and see your real, explainable match for each.
        </p>
      </div>
      <OpportunityListView detailBasePath="/student/opportunities" />
    </div>
  );
}
