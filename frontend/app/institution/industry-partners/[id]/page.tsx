import { IndustryPartnerDetail } from "@/components/institution/industry-partners/industry-partner-detail";

export default async function InstitutionIndustryPartnerPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return <IndustryPartnerDetail industryId={id} />;
}
