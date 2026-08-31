import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApplicantTable } from "@/components/opportunities/applicant-table";

export default async function ApplicantsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <Button variant="ghost" size="sm" className="w-fit" render={<Link href="/industry/opportunities" />} nativeButton={false}>
        <ArrowLeft /> Back to My Opportunities
      </Button>
      <div>
        <h1 className="text-xl font-semibold">Applicants</h1>
        <p className="text-sm text-muted-foreground">
          Sorted by match — highest first. Each score is computed fresh from real assessment evidence.
        </p>
      </div>
      <ApplicantTable opportunityId={id} />
    </div>
  );
}
