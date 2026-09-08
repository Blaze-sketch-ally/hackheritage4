import { InstitutionInternshipDetailView } from "@/components/institution/internships/internship-detail-view";

export default async function InstitutionInternshipPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return <InstitutionInternshipDetailView internshipId={id} />;
}
