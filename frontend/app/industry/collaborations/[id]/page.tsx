import { CollaborationDetailView } from "@/components/industry/collaborations/collaboration-detail-view";

export default async function IndustryCollaborationDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ edit?: string | string[] }>;
}) {
  const { id } = await params;
  const sp = await searchParams;

  return (
    <div className="mx-auto max-w-3xl">
      <CollaborationDetailView collaborationId={id} initialEdit={sp.edit === "1"} />
    </div>
  );
}
