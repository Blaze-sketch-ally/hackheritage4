import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MentorshipOpportunityDetailView } from "@/components/student/mentorship-opportunities/mentorship-opportunity-detail-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentMentorshipOpportunityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { id } = await params;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Button
        variant="ghost"
        size="sm"
        className="w-fit"
        render={<Link href="/student/mentorship-opportunities" />}
        nativeButton={false}
      >
        <ArrowLeft /> Back to Mentorship Opportunities
      </Button>
      <MentorshipOpportunityDetailView mentorshipId={id} />
    </div>
  );
}
