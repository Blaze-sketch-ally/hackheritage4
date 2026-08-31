import Link from "next/link";
import { ArrowLeft, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EditOpportunityView } from "@/components/opportunities/edit-opportunity-view";

export default async function EditOpportunityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" render={<Link href="/industry/opportunities" />} nativeButton={false}>
          <ArrowLeft /> Back
        </Button>
        <Button variant="outline" size="sm" render={<Link href={`/industry/opportunities/${id}/applicants`} />} nativeButton={false}>
          <Users /> View Applicants
        </Button>
      </div>
      <EditOpportunityView opportunityId={id} />
    </div>
  );
}
