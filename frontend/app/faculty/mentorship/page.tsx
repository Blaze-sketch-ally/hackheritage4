import { redirect } from "next/navigation";
import { FacultyMentorshipView } from "@/components/faculty/faculty-mentorship-view";
import { createClient } from "@/lib/supabase/server";

export default async function FacultyMentorshipPage() {
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
          Mentor students who request you, or request a student you&apos;d like to mentor.
        </p>
      </div>
      <FacultyMentorshipView />
    </div>
  );
}
