import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { JobTrainingDetailView } from "@/components/student/job-training/job-training-detail-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentJobTrainingEnrollmentPage({
  params,
}: {
  params: Promise<{ enrollmentId: string }>;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { enrollmentId } = await params;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <Button
        variant="ghost"
        size="sm"
        className="w-fit"
        render={<Link href="/student/job-training" />}
        nativeButton={false}
      >
        <ArrowLeft /> Back to Job Training
      </Button>
      <JobTrainingDetailView enrollmentId={enrollmentId} />
    </div>
  );
}
