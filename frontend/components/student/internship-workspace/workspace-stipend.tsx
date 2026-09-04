"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { StipendStatusBadge } from "@/components/common/stipend-status-badge";
import { ApiError } from "@/lib/api";
import { getMyWorkspaceStipend } from "@/lib/student/internship-workspace";
import type { Stipend } from "@/types/internship-stipend";

function fmt(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function money(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(amount);
  } catch {
    return `${amount} ${currency}`;
  }
}

const STATUS_LEAD: Record<string, string> = {
  PENDING: "Your industry has configured a stipend for this internship.",
  APPROVED: "Your stipend has been approved.",
  RELEASED: "Your industry has marked this stipend as released in the portal.",
  CANCELLED: "This stipend record was cancelled.",
};

/** The student's own stipend record (RECORD-KEEPING ONLY -- this portal
 * never moves money; "released" means the industry recorded a
 * disbursement, not that a payment was processed). Read-only. */
export function WorkspaceStipend({ workspaceId }: { workspaceId: string }) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "error"; message: string }
    | { status: "ready"; stipend: Stipend | null }
  >({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    getMyWorkspaceStipend(workspaceId)
      .then((summary) => {
        if (!cancelled) setState({ status: "ready", stipend: summary.stipend });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load stipend status.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  if (state.status === "loading") {
    return (
      <section aria-busy="true" aria-label="Loading stipend status">
        <div className="h-16 animate-pulse rounded-lg bg-muted" />
      </section>
    );
  }

  if (state.status === "error") {
    return <p className="text-sm text-destructive">{state.message}</p>;
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
        Stipend
      </h2>
      <Card>
        <CardContent className="flex flex-col gap-2 py-4">
          {state.stipend === null ? (
            <p className="text-sm text-muted-foreground">No stipend information available yet.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-lg font-semibold">
                  {money(state.stipend.amount, state.stipend.currency)}
                </p>
                <StipendStatusBadge status={state.stipend.disbursement_status} />
              </div>
              <p className="text-sm text-muted-foreground">
                {STATUS_LEAD[state.stipend.disbursement_status] ?? ""}
              </p>
              {state.stipend.disbursement_status === "RELEASED" && (
                <p className="text-sm text-muted-foreground">
                  Released {fmt(state.stipend.released_at)}
                  {state.stipend.reference ? ` · Reference: ${state.stipend.reference}` : ""}
                </p>
              )}
              {state.stipend.notes ? (
                <p className="text-sm whitespace-pre-wrap text-muted-foreground">
                  {state.stipend.notes}
                </p>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
