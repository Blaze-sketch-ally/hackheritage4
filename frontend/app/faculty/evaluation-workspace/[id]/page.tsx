import { redirect } from "next/navigation";
import { CapabilityGate } from "@/components/faculty/capability-gate";
import { EvaluationDetailView } from "@/components/faculty/evaluation-detail-view";
import { createClient } from "@/lib/supabase/server";

export default async function FacultyEvaluationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <div className="mx-auto max-w-2xl">
      <CapabilityGate
        capability="assessment_evaluator"
        deniedMessage="Ask an Admin to grant you the Evaluator capability to access this workspace."
      >
        <EvaluationDetailView evaluationId={id} />
      </CapabilityGate>
    </div>
  );
}
