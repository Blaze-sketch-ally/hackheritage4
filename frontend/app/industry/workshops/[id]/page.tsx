import { WorkshopDetailView } from "@/components/industry/workshops/workshop-detail-view";

export default async function IndustryWorkshopDetailPage({
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
      <WorkshopDetailView workshopId={id} initialEdit={sp.edit === "1"} />
    </div>
  );
}
