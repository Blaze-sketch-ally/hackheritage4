import Link from "next/link";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MyOpportunitiesView } from "@/components/opportunities/my-opportunities-view";

export default function IndustryOpportunitiesPage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">My Opportunities</h1>
          <p className="text-sm text-muted-foreground">Manage your job and internship postings.</p>
        </div>
        <Button render={<Link href="/industry/opportunities/new" />} nativeButton={false}>
          <Plus /> Post an Opportunity
        </Button>
      </div>
      <MyOpportunitiesView />
    </div>
  );
}
