import { redirect } from "next/navigation";
import { MyInternshipsView } from "@/components/student/internship-workspace/my-internships-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentMyInternshipsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">My Internships</h1>
        <p className="text-sm text-muted-foreground">
          Remote and Hybrid internships you&apos;ve been selected for. Accept an offer
          to open its training workspace.
        </p>
      </div>
      <MyInternshipsView />
    </div>
  );
}
