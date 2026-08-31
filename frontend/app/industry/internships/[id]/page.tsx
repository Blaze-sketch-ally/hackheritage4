import { InternshipDetailView } from "@/components/industry/internships/internship-detail-view";

export default async function IndustryInternshipDetailPage({
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
      <InternshipDetailView internshipId={id} initialEdit={sp.edit === "1"} />
    </div>
  );
}
