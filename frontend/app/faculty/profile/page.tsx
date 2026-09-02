import { redirect } from "next/navigation";
import { FacultyProfileView } from "@/components/faculty/faculty-profile-view";
import { createClient } from "@/lib/supabase/server";

export default async function FacultyProfilePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The faculty layout already guarantees an authenticated FACULTY user
  // reaches this point — this is a defensive fallback, not a second check.
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Your profile</h1>
        <p className="text-sm text-muted-foreground">
          Keep your academic details up to date so students and collaborators know who you are.
        </p>
      </div>
      <FacultyProfileView />
    </div>
  );
}
