import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MentorshipDetailView } from "@/components/student/mentorship/mentorship-detail-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentMentorshipDetailPage({
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
        render={<Link href="/student/mentorship" />}
        nativeButton={false}
      >
        <ArrowLeft /> Back to Mentorship
      </Button>
      <MentorshipDetailView mentorshipId={id} />
    </div>
  );
}
