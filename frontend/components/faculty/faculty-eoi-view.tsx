"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Loader2, RefreshCw, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { listMyExpressions, withdrawExpression } from "@/lib/faculty/opportunities";
import { OPPORTUNITY_SOURCE_LABELS } from "@/types/faculty-opportunity";
import { EOI_STATUS_LABELS, type EoiStatus, type FacultyOpportunityExpression } from "@/types/faculty-opportunity-expression";
import { ENGAGEMENT_STATUS_LABELS } from "@/types/faculty-engagement";

/** "My EOIs" -- the caller's own expressions of interest against
 * Industry/Institution Faculty opportunities. Deliberately separate from
 * FacultyApplicationsView (industry_collaborations): the two represent
 * different directions (Faculty-initiated interest in a public listing,
 * vs. an Industry-initiated proposal addressed directly at this Faculty
 * member) per the approved F3.4 architecture -- see
 * app/faculty/applications/page.tsx, which renders both as separate tabs
 * rather than conflating them. */

const WITHDRAWABLE: readonly EoiStatus[] = ["SUBMITTED", "UNDER_REVIEW"];

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; expressions: FacultyOpportunityExpression[] };

export function FacultyEoiView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { expressions } = await listMyExpressions();
        if (cancelled) return;
        setState({ status: "ready", expressions });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load your expressions of interest.",
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  async function handleWithdraw(expression: FacultyOpportunityExpression) {
    setActioningId(expression.id);
    setActionError(null);
    try {
      const updated = await withdrawExpression(expression.source, expression.id);
      setState((prev) =>
        prev.status === "ready"
          ? { ...prev, expressions: prev.expressions.map((e) => (e.id === expression.id ? updated : e)) }
          : prev,
      );
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not withdraw this expression of interest.");
    } finally {
      setActioningId(null);
    }
  }

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading your expressions of interest…
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">{state.message}</p>
          <Button size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { expressions } = state;

  if (expressions.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          You haven&apos;t expressed interest in any opportunities yet.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {actionError && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="size-3.5 shrink-0" /> {actionError}
        </p>
      )}
      {expressions.map((e) => {
        const busy = actioningId === e.id;
        const canWithdraw = WITHDRAWABLE.includes(e.status);
        return (
          <Card key={e.id}>
            <CardContent className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="font-medium">{e.opportunity_title ?? "Opportunity"}</p>
                <p className="text-sm text-muted-foreground">
                  {OPPORTUNITY_SOURCE_LABELS[e.source]} ·{" "}
                  {e.created_at ? new Date(e.created_at).toLocaleDateString() : "—"}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <StatusBadge status={e.status} />
                {e.engagement && (
                  <span className="text-xs text-muted-foreground">
                    Engagement: {ENGAGEMENT_STATUS_LABELS[e.engagement.status]}
                  </span>
                )}
                {canWithdraw && (
                  <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleWithdraw(e)}>
                    <X className="size-3.5" /> Withdraw
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }: { status: EoiStatus }) {
  const label = EOI_STATUS_LABELS[status];
  if (status === "ACCEPTED") {
    return <Badge className="bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500">{label}</Badge>;
  }
  if (status === "REJECTED" || status === "WITHDRAWN") return <Badge variant="destructive">{label}</Badge>;
  if (status === "UNDER_REVIEW") return <Badge variant="secondary">{label}</Badge>;
  return <Badge variant="outline">{label}</Badge>;
}
