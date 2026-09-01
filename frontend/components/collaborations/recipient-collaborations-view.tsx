"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Inbox, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import {
  acceptCollaboration,
  getIncomingCollaborations,
  rejectCollaboration,
} from "@/lib/industry/collaborations";
import {
  COLLABORATION_STATUS_LABELS,
  type IndustryCollaboration,
} from "@/types/industry-collaboration";
import { CollaborationStatusBadge } from "@/components/industry/collaborations/collaboration-status-badge";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; collaborations: IndustryCollaboration[] };

type RecipientAction = "accept" | "reject";

const ACTION_COPY: Record<
  RecipientAction,
  { title: string; description: string; confirm: string; destructive: boolean; done: string }
> = {
  accept: {
    title: "Accept this collaboration proposal?",
    description: "The industry initiator will be notified you've agreed.",
    confirm: "Accept",
    destructive: false,
    done: "Proposal accepted.",
  },
  reject: {
    title: "Reject this collaboration proposal?",
    description: "This can't be undone.",
    confirm: "Reject",
    destructive: true,
    done: "Proposal rejected.",
  },
};

const RUNNERS: Record<RecipientAction, (id: string) => Promise<IndustryCollaboration>> = {
  accept: acceptCollaboration,
  reject: rejectCollaboration,
};

function formatDate(value: string | null): string {
  if (!value) return "Not set";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Minimum recipient-side UI (Faculty and Institution both use this same
 * component, mounted from their own portal's page) -- see incoming
 * proposals, view their details inline, and accept/reject. No detail
 * route, no broader collaboration-management ecosystem, per the approved
 * Phase 10E scope.
 */
export function RecipientCollaborationsView({ heading }: { heading: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  const [pending, setPending] = useState<{ id: string; action: RecipientAction } | null>(null);
  const [confirming, setConfirming] = useState<{ id: string; action: RecipientAction } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getIncomingCollaborations()
      .then(({ collaborations }) => {
        if (!cancelled) setState({ status: "ready", collaborations });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your collaborations."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function runAction(id: string, action: RecipientAction) {
    setConfirming(null);
    setPending({ id, action });
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await RUNNERS[action](id);
      setState((prev) =>
        prev.status === "ready"
          ? { ...prev, collaborations: prev.collaborations.map((c) => (c.id === id ? updated : c)) }
          : prev,
      );
      setActionSuccess(ACTION_COPY[action].done);
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{heading}</h1>
        <p className="text-sm text-muted-foreground">
          Collaboration proposals from Industry partners.
        </p>
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading your collaborations…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {state.error.status === 401
                  ? "Your session has expired. Please sign in again."
                  : "Could not load your collaborations."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status !== 401 ? (
              <Button variant="outline" size="sm" onClick={reload}>
                <RefreshCw className="size-3.5" /> Try again
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        state.collaborations.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No collaboration proposals yet"
            description="Proposals sent to you by Industry partners will appear here."
          />
        ) : (
          <div className="space-y-3">
            {state.collaborations.map((collaboration) => (
              <Card key={collaboration.id}>
                <CardContent className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <p className="font-medium">{collaboration.title}</p>
                      {collaboration.industry_name ? (
                        <p className="truncate text-sm text-foreground">
                          From {collaboration.industry_name}
                        </p>
                      ) : null}
                      <p className="text-xs text-muted-foreground">
                        Received {formatDate(collaboration.created_at)}
                      </p>
                    </div>
                    <CollaborationStatusBadge status={collaboration.status} />
                  </div>
                  <p className="text-sm whitespace-pre-line text-muted-foreground">
                    {collaboration.description}
                  </p>
                  {collaboration.status === "SENT" ? (
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <Button
                        size="sm"
                        onClick={() => setConfirming({ id: collaboration.id, action: "accept" })}
                        disabled={pending?.id === collaboration.id}
                      >
                        Accept
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setConfirming({ id: collaboration.id, action: "reject" })}
                        disabled={pending?.id === collaboration.id}
                      >
                        Reject
                      </Button>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Status: {COLLABORATION_STATUS_LABELS[collaboration.status]}
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )
      ) : null}

      <ConfirmationDialog
        open={!!confirming}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={confirming ? ACTION_COPY[confirming.action].title : ""}
        description={confirming ? ACTION_COPY[confirming.action].description : undefined}
        confirmLabel={confirming ? ACTION_COPY[confirming.action].confirm : "Confirm"}
        destructive={confirming ? ACTION_COPY[confirming.action].destructive : false}
        loading={!!pending}
        onConfirm={() => confirming && runAction(confirming.id, confirming.action)}
      />
    </div>
  );
}
