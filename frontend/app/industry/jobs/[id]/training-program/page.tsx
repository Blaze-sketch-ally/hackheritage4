import { JobTrainingProgramView } from "@/components/industry/job-training-program/job-training-program-view";

export default async function IndustryJobTrainingProgramPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-3xl">
      <JobTrainingProgramView jobId={id} />
    </div>
  );
}
