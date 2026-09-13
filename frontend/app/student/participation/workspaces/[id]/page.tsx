import { StudentWorkspaceView } from "@/components/student/participation/workspace-view";

/**
 * Direct-by-id entry point into a Participation Workspace (Project/
 * Training/Workshop) -- for callers that already know the workspace_id
 * itself, not just the opportunity id. The only existing student
 * workspace routes (app/student/{industry-projects,trainings,workshops}/
 * [id]/workspace/page.tsx) resolve FROM an opportunity id via
 * WorkspaceForOpportunity; a participation_workspaces notification
 * (notification_producer.emit_participation_*, migration 066) carries the
 * workspace_id directly, so no such resolution is needed or possible here.
 * Renders the exact same StudentWorkspaceView those routes render --
 * no new workspace logic, just a second, more direct way in.
 */
export default async function StudentParticipationWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-4xl">
      <StudentWorkspaceView workspaceId={id} />
    </div>
  );
}
