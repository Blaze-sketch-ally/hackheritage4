import { ParticipantDetailView } from "@/components/industry/participation/participant-detail-view";

export default async function ParticipantWorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-4xl">
      <ParticipantDetailView workspaceId={id} />
    </div>
  );
}
