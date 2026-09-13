import { WorkspaceForOpportunity } from "@/components/student/participation/workspace-for-opportunity";

export default async function StudentProjectWorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-4xl">
      <WorkspaceForOpportunity kind="PROJECT" opportunityId={id} backHref="/student/industry-projects" />
    </div>
  );
}
