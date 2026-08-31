import { JobDetailView } from "@/components/industry/jobs/job-detail-view";

export default async function IndustryJobDetailPage({
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
      <JobDetailView jobId={id} initialEdit={sp.edit === "1"} />
    </div>
  );
}
