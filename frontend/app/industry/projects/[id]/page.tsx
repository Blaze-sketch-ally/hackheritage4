import { ProjectDetailView } from "@/components/industry/projects/project-detail-view";

export default async function IndustryProjectDetailPage({
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
      <ProjectDetailView projectId={id} initialEdit={sp.edit === "1"} />
    </div>
  );
}
