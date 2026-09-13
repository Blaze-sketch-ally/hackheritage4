import { WorkshopDetailView } from "@/components/student/workshops/workshop-detail-view";

export default async function StudentWorkshopDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-3xl">
      <WorkshopDetailView workshopId={id} />
    </div>
  );
}
