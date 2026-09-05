import { EvaluatorAssignmentView } from "@/components/admin/evaluator-assignment-view";

// The /admin/* layout (app/admin/layout.tsx) already guards this page to
// role === "ADMIN" server-side; EvaluatorAssignmentView is a management
// UI over an already-secured API (require_admin() +
// create_evaluator_assignment()/revoke_evaluator_assignment(),
// 045_evaluation_foundation.sql), never a second authorization decision.
//
// Phase 2 (Evaluator Assignment): replaces the previous "Coming Soon"
// stub with the real evaluator-assignment management area -- this was
// already the intended "AIC assessment management" destination (the
// route existed, unlinked, before this phase).
export default function Page() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-8">
      <div>
        <h1 className="text-xl font-semibold">Evaluator assignments</h1>
        <p className="text-sm text-muted-foreground">
          Assign Faculty evaluators to AI-evaluated questions within completed student attempts.
        </p>
      </div>
      <EvaluatorAssignmentView />
    </div>
  );
}
