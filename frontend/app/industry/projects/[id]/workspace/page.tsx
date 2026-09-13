import { WorkspaceManageView } from "@/components/industry/participation/workspace-manage-view";

export default async function ProjectWorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Project Workspace</h1>
        <p className="text-sm text-muted-foreground">Manage modules, resources, assignments, and participants.</p>
      </div>
      <WorkspaceManageView kind="PROJECT" opportunityId={id} />
    </div>
  );
}
