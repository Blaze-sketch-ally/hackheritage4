import { redirect } from "next/navigation";
import { MentorshipListView } from "@/components/student/mentorship/mentorship-list-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentMentorshipPage() {
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
        <h1 className="text-xl font-semibold">Mentorship</h1>
        <p className="text-sm text-muted-foreground">
          Multi-month mentoring engagements published by industry partners.
        </p>
      </div>
      <MentorshipListView />
    </div>
  );
}
