import { redirect } from "next/navigation";
import { CapabilityGate } from "@/components/faculty/capability-gate";
import { EvaluationWorkspaceView } from "@/components/faculty/evaluation-workspace-view";
import { createClient } from "@/lib/supabase/server";

// Phase 2: real workspace, replacing Phase 1's honest placeholder.
export default async function FacultyEvaluationWorkspacePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Evaluation Workspace</h1>
        <p className="text-sm text-muted-foreground">
          Evaluate student answers you&apos;ve been assigned to review.
        </p>
      </div>
      <CapabilityGate
        capability="assessment_evaluator"
        deniedMessage="Ask an Admin to grant you the Evaluator capability to access this workspace."
      >
        <EvaluationWorkspaceView />
      </CapabilityGate>
    </div>
  );
}
