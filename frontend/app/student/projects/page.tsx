import { redirect } from "next/navigation";
import { ProjectsView } from "@/components/student/portfolio/projects-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentProjectsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return <ProjectsView />;
}
