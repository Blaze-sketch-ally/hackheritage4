import { InstitutionCollaborationDetail } from "@/components/institution/collaborations/institution-collaboration-detail";

export default async function InstitutionCollaborationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return <InstitutionCollaborationDetail collaborationId={id} />;
}
