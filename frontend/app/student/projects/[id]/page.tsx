import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProjectDetailView } from "@/components/student/portfolio/project-detail-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { id } = await params;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Button
        variant="ghost"
        size="sm"
        className="w-fit"
        render={<Link href="/student/projects" />}
        nativeButton={false}
      >
        <ArrowLeft /> Back to Projects
      </Button>
      <ProjectDetailView projectId={id} />
    </div>
  );
}
