"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorState } from "@/components/common/error-state";
import { ApiError } from "@/lib/api";
import { listReconciliationCases } from "@/lib/faculty/reconciliation";
import type { ReconciliationCaseSummary } from "@/types/reconciliation";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; cases: ReconciliationCaseSummary[] };

/**
 * READ-ONLY list of every current NEEDS_RECONCILIATION case (Faculty
 * Assessment Governance audit). Every current assessment_moderator sees
 * every current case -- an explicit, documented interim default (see
 * 067_assessment_reconciliation_visibility.sql's own header), not a
 * final per-moderator assignment model. There is no resolve/decide
 * action anywhere on this page: this phase implements visibility only.
 */
export function ReconciliationListView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listReconciliationCases()
      .then(({ cases }) => {
        if (!cancelled) setState({ status: "ready", cases });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: err instanceof ApiError ? err.message : "Could not load reconciliation cases.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (state.status === "loading") {
    return (
      <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading reconciliation cases">
        {[0, 1, 2].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="space-y-2 py-4">
              <div className="h-4 w-1/3 rounded bg-muted" />
              <div className="h-3 w-2/3 rounded bg-muted" />
            </CardContent>
          </Card>
        ))}
      </div>
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

  if (state.cases.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <ShieldCheck className="size-8" aria-hidden="true" />
          <p className="font-medium text-foreground">No reconciliation cases.</p>
          <p className="text-sm">
            Every assessment attempt currently has agreeing evaluator marks.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {state.cases.map((c) => (
        <Link
          key={`${c.attempt_id}-${c.question_id}`}
          href={`/faculty/reconciliation/${encodeURIComponent(c.attempt_id)}`}
          className="block rounded-lg border border-amber-500/20 bg-amber-500/[0.03] px-4 py-3 transition-colors hover:bg-amber-500/[0.06] focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold">{c.assessment_title}</p>
                <Badge variant="outline">{c.student_label}</Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{c.question_text}</p>
              <p className="mt-1 text-xs text-muted-foreground">{c.points} points</p>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
