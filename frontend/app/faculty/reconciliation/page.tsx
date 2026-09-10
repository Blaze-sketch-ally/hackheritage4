import { redirect } from "next/navigation";
import { CapabilityGate } from "@/components/faculty/capability-gate";
import { ReconciliationListView } from "@/components/faculty/reconciliation/reconciliation-list-view";
import { createClient } from "@/lib/supabase/server";

// Faculty Assessment Governance audit: READ-ONLY visibility only -- see
// that phase's report for why a resolution/decision mechanism is a
// genuine, unresolved product decision, not implemented here.
export default async function FacultyReconciliationPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Reconciliation</h1>
        <p className="text-sm text-muted-foreground">
          Assessment attempts where evaluators disagree, awaiting a governed decision.
        </p>
      </div>
      <CapabilityGate
        capability="assessment_moderator"
        deniedMessage="Ask an Admin to grant you the Moderator capability to access reconciliation cases."
      >
        <ReconciliationListView />
      </CapabilityGate>
    </div>
  );
}
