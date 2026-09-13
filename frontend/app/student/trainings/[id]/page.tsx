import { TrainingDetailView } from "@/components/student/training/training-detail-view";

export default async function StudentTrainingDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-3xl">
      <TrainingDetailView trainingId={id} />
    </div>
  );
}
