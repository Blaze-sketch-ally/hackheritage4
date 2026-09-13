import { IndustryProjectDetailView } from "@/components/student/industry-projects/industry-project-detail-view";

export default async function StudentIndustryProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-3xl">
      <IndustryProjectDetailView projectId={id} />
    </div>
  );
}
