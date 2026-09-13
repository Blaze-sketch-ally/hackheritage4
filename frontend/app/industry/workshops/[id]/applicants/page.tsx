import { WorkshopApplicantsView } from "@/components/industry/workshops/workshop-applicants-view";

export default async function WorkshopApplicantsPage({
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
          Students who registered for this workshop.
        </p>
      </div>
      <WorkshopApplicantsView workshopId={id} />
    </div>
  );
}
