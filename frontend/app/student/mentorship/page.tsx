import { redirect } from "next/navigation";
import { StudentMentorshipView } from "@/components/student/student-mentorship-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentMentorshipPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Mentorship</h1>
        <p className="text-sm text-muted-foreground">
          Request a Faculty mentor, or respond to a Faculty member who has requested to mentor you.
        </p>
      </div>
      <StudentMentorshipView />
    </div>
  );
}
