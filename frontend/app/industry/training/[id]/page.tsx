import { TrainingDetailView } from "@/components/industry/training/training-detail-view";

export default async function IndustryTrainingDetailPage({
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
      <TrainingDetailView trainingId={id} initialEdit={sp.edit === "1"} />
    </div>
  );
}
