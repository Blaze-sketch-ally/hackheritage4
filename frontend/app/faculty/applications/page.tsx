import { redirect } from "next/navigation";
import { FacultyApplicationsTabs } from "@/components/faculty/faculty-applications-tabs";
import { createClient } from "@/lib/supabase/server";

export default async function FacultyApplicationsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Applications</h1>
        <p className="text-sm text-muted-foreground">
          Your expressions of interest, and collaboration requests Industry has sent you.
        </p>
      </div>
      <FacultyApplicationsTabs />
    </div>
  );
}
