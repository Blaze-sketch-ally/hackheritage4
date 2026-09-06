import { redirect } from "next/navigation";
import { MentorshipOpportunityListView } from "@/components/student/mentorship-opportunities/mentorship-opportunity-list-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentMentorshipOpportunitiesPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Mentorship Opportunities</h1>
        <p className="text-sm text-muted-foreground">
          Multi-month mentoring engagements published by industry partners.
        </p>
      </div>
      <MentorshipOpportunityListView />
    </div>
  );
}
