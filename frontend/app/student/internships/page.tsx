import { redirect } from "next/navigation";
import { OpportunityListView } from "@/components/opportunities/opportunity-list-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentInternshipsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Internships</h1>
        <p className="text-sm text-muted-foreground">Internship postings matched against your assessed skills.</p>
      </div>
      <OpportunityListView lockedType="INTERNSHIP" detailBasePath="/student/internships" />
    </div>
  );
}
