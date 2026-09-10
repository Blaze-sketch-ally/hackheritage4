"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/common/error-state";
import { ApiError } from "@/lib/api";
import { getReconciliationCase } from "@/lib/faculty/reconciliation";
import type { ReconciliationEvaluatorMark } from "@/types/reconciliation";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "not_found" }
  | { status: "ready"; marks: ReconciliationEvaluatorMark[] };

/**
 * READ-ONLY comparison of the conflicting FINALIZED evaluator marks
 * behind one reconciliation case (Faculty Assessment Governance audit).
 * There is deliberately no "resolve" / "decide" action anywhere on this
 * page -- this phase implements visibility only (see the audit report
 * for why a resolution mechanism is a genuine, unresolved product
 * decision). Evaluator A's mark and evaluator B's mark are shown side by
 * side, both fully preserved -- never averaged, never a chosen value.
 */
export function ReconciliationDetailView({ attemptId }: { attemptId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getReconciliationCase(attemptId)
      .then(({ marks }) => {
        if (!cancelled) setState({ status: "ready", marks });
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setState({ status: "not_found" });
          } else {
            setState({
              status: "error",
              message: err instanceof ApiError ? err.message : "Could not load this reconciliation case.",
            });
          }
        }
      });
    return () => {
      cancelled = true;
    };
  }, [attemptId, reloadKey]);

  if (state.status === "loading") {
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading reconciliation case">
        {[0, 1].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="h-24 py-4" />
          </Card>
        ))}
      </div>
    );
  }

  if (state.status === "not_found") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <p className="font-medium text-foreground">This is not a current reconciliation case.</p>
          <p className="text-sm">It may have already been resolved, or the id is incorrect.</p>
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    return (
      <ErrorState
        message={state.message}
        onRetry={() => {
          setState({ status: "loading" });
          setReloadKey((k) => k + 1);
        }}
      />
    );
  }

  // Group by question -- one attempt can have more than one conflicting question.
  const byQuestion = new Map<string, ReconciliationEvaluatorMark[]>();
  for (const mark of state.marks) {
    const existing = byQuestion.get(mark.question_id) ?? [];
    existing.push(mark);
    byQuestion.set(mark.question_id, existing);
  }

  return (
    <div className="flex flex-col gap-4">
      {[...byQuestion.entries()].map(([questionId, marks]) => (
        <Card key={questionId}>
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-4 text-amber-600 dark:text-amber-400" aria-hidden="true" />
              <CardTitle className="text-base">{marks[0].question_text}</CardTitle>
            </div>
            <p className="text-sm text-muted-foreground">{marks[0].points} points</p>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {marks.map((mark) => (
              <div key={mark.evaluator_id} className="rounded-lg border p-3">
                <div className="flex items-center justify-between gap-2">
                  <Badge variant="outline">Evaluator {mark.evaluator_id.slice(0, 8)}</Badge>
                  <span className="text-sm font-semibold">{mark.awarded_marks} pts</span>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">Rubric: {mark.rubric_name}</p>
                {mark.feedback && (
                  <p className="mt-2 text-sm whitespace-pre-wrap text-muted-foreground">{mark.feedback}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
