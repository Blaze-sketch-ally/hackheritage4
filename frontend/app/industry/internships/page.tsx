import Link from "next/link";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MyOpportunitiesView } from "@/components/opportunities/my-opportunities-view";

// A filtered view over the same unified opportunity system as
// /industry/opportunities -- never a second implementation.
export default function IndustryInternshipsPage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Internships</h1>
          <p className="text-sm text-muted-foreground">Manage your internship postings.</p>
        </div>
        <Button render={<Link href="/industry/internships/create" />} nativeButton={false}>
          <Plus /> Post an Internship
        </Button>
      </div>
      <MyOpportunitiesView lockedType="INTERNSHIP" />
    </div>
  );
}
