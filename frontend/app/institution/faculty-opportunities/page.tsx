import { redirect } from "next/navigation";
import { InstitutionFacultyOpportunitiesView } from "@/components/institution/institution-faculty-opportunities-view";
import { createClient } from "@/lib/supabase/server";

export default async function InstitutionFacultyOpportunitiesPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Faculty Opportunities</h1>
        <p className="text-sm text-muted-foreground">
          Create opportunities for Faculty participation and review expressions of interest.
        </p>
      </div>
      <InstitutionFacultyOpportunitiesView />
    </div>
  );
}
