"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { listMyWorkspaces } from "@/lib/student/participation";
import { OPPORTUNITY_FK, type ParticipationKind } from "@/types/participation";
import { StudentWorkspaceView } from "@/components/student/participation/workspace-view";

/** Resolves "my workspace for opportunity X" (the student knows the
 * Project/Training/Workshop id, not the workspace id) by listing their
 * own workspaces for this `kind` and matching on the opportunity FK --
 * then renders the real workspace view. No new backend endpoint: reuses
 * GET /student/participation/workspaces?kind=. */
export function WorkspaceForOpportunity({ kind, opportunityId, backHref }: { kind: ParticipationKind; opportunityId: string; backHref: string }) {
  const [state, setState] = useState<{ status: "loading" } | { status: "error"; message: string } | { status: "none" } | { status: "ready"; workspaceId: string }>({
    status: "loading",
  });

  useEffect(() => {
    let cancelled = false;
    listMyWorkspaces({ kind })
      .then(({ workspaces }) => {
        if (cancelled) return;
        const fk = OPPORTUNITY_FK[kind];
        const match = workspaces.find((w) => w[fk] === opportunityId);
        setState(match ? { status: "ready", workspaceId: match.id } : { status: "none" });
      })
      .catch((err) => {
        if (!cancelled) setState({ status: "error", message: err instanceof ApiError ? err.message : "Could not load your workspace." });
      });
    return () => {
      cancelled = true;
    };
  }, [kind, opportunityId]);

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
          Loading…
        </CardContent>
      </Card>
    );
  }
  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">{state.message}</p>
        </CardContent>
      </Card>
    );
  }
  if (state.status === "none") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
          <p className="font-medium">No workspace available yet</p>
          <p className="text-sm text-muted-foreground">
            A workspace opens here once you&apos;re selected/accepted for this opportunity.
          </p>
          <Link href={backHref} className="text-sm text-indigo-600 hover:underline dark:text-indigo-400">
            Back
          </Link>
        </CardContent>
      </Card>
    );
  }

  return <StudentWorkspaceView workspaceId={state.workspaceId} />;
}
