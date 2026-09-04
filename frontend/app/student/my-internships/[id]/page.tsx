import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { InternshipWorkspaceView } from "@/components/student/internship-workspace/internship-workspace-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentInternshipWorkspacePage({
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
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <Button
        variant="ghost"
        size="sm"
        className="w-fit"
        render={<Link href="/student/my-internships" />}
        nativeButton={false}
      >
        <ArrowLeft /> Back to My Internships
      </Button>
      <InternshipWorkspaceView workspaceId={id} />
    </div>
  );
}
