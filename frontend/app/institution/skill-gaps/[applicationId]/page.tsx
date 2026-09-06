import { SkillGapDetail } from "@/components/institution/skill-gaps/skill-gap-detail";

export default async function InstitutionSkillGapDetailPage({
  params,
}: {
  params: Promise<{ applicationId: string }>;
}) {
  const { applicationId } = await params;

  return <SkillGapDetail applicationId={applicationId} />;
}
