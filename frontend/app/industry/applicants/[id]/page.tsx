import { ApplicationDetailView } from "@/components/industry/applicants/application-detail-view";

export default async function IndustryApplicationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-3xl">
      <ApplicationDetailView applicationId={id} />
    </div>
  );
}
