import { InstitutionEventDetailView } from "@/components/institution/events/event-detail-view";

export default async function InstitutionEventPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return <InstitutionEventDetailView eventId={id} />;
}
