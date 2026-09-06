import { redirect } from "next/navigation";
import { OpportunityListView } from "@/components/student/opportunities/opportunity-list-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentInternshipsPage() {
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
        <h1 className="text-xl font-semibold">Internships</h1>
        <p className="text-sm text-muted-foreground">
          Browse published internships and see your real skill match for each.
        </p>
      </div>
      <OpportunityListView sourceType="INTERNSHIP" detailBasePath="/student/internships" />
    </div>
  );
}
