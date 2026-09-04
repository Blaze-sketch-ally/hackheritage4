import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AssignmentDetailView } from "@/components/student/internship-workspace/assignment-detail-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentWorkspaceAssignmentPage({
  params,
}: {
  params: Promise<{ id: string; assignmentId: string }>;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { id, assignmentId } = await params;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Button
        variant="ghost"
        size="sm"
        className="w-fit"
        render={<Link href={`/student/my-internships/${id}`} />}
        nativeButton={false}
      >
        <ArrowLeft /> Back to workspace
      </Button>
      <AssignmentDetailView workspaceId={id} assignmentId={assignmentId} />
    </div>
  );
}
