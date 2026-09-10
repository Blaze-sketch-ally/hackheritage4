import { redirect } from "next/navigation";
import { JobTrainingListView } from "@/components/student/job-training/job-training-list-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentJobTrainingPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Job Training</h1>
        <p className="text-sm text-muted-foreground">
          Training programs from companies that have selected you for a job. This is
          separate from Learning &amp; Courses and from Internship Workspaces.
        </p>
      </div>
      <JobTrainingListView />
    </div>
  );
}
