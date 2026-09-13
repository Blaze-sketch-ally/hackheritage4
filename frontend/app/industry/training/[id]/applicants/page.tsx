import { TrainingApplicantsView } from "@/components/industry/training/training-applicants-view";

export default async function TrainingApplicantsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Applicants</h1>
        <p className="text-sm text-muted-foreground">
          Students who registered for this training program.
        </p>
      </div>
      <TrainingApplicantsView trainingId={id} />
    </div>
  );
}
