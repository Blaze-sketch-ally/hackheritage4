import { redirect } from "next/navigation";
import { MyApplicationsView } from "@/components/student/opportunities/my-applications-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentApplicationsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">My Applications</h1>
        <p className="text-sm text-muted-foreground">
          Track the status of every internship and job you&apos;ve applied to.
        </p>
      </div>
      <MyApplicationsView />
    </div>
  );
}
