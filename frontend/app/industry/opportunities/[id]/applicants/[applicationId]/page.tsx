import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApplicantDetailView } from "@/components/opportunities/applicant-detail-view";

export default async function ApplicantDetailPage({
  params,
}: {
  params: Promise<{ id: string; applicationId: string }>;
}) {
  const { id, applicationId } = await params;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <Button
        variant="ghost"
        size="sm"
        className="w-fit"
        render={<Link href={`/industry/opportunities/${id}/applicants`} />}
        nativeButton={false}
      >
        <ArrowLeft /> Back to Applicants
      </Button>
      <ApplicantDetailView opportunityId={id} applicationId={applicationId} />
    </div>
  );
}
