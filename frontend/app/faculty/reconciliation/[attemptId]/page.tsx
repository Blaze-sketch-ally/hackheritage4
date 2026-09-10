import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { CapabilityGate } from "@/components/faculty/capability-gate";
import { ReconciliationDetailView } from "@/components/faculty/reconciliation/reconciliation-detail-view";
import { createClient } from "@/lib/supabase/server";

export default async function FacultyReconciliationDetailPage({
  params,
}: {
  params: Promise<{ attemptId: string }>;
}) {
  const { attemptId } = await params;

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Link
        href="/faculty/reconciliation"
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> All reconciliation cases
      </Link>
      <CapabilityGate
        capability="assessment_moderator"
        deniedMessage="Ask an Admin to grant you the Moderator capability to access reconciliation cases."
      >
        <ReconciliationDetailView attemptId={attemptId} />
      </CapabilityGate>
    </div>
  );
}
