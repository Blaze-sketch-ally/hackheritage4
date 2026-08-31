import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { OpportunityForm } from "@/components/opportunities/opportunity-form";

export default function NewOpportunityPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <Button variant="ghost" size="sm" className="w-fit" render={<Link href="/industry/opportunities" />} nativeButton={false}>
        <ArrowLeft /> Back to My Opportunities
      </Button>
      <div>
        <h1 className="text-xl font-semibold">Post an Opportunity</h1>
        <p className="text-sm text-muted-foreground">
          Starts as a draft — add required skills and publish when ready.
        </p>
      </div>
      <OpportunityForm mode="create" />
    </div>
  );
}
