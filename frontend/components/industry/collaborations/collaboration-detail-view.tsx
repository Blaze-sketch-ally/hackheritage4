"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, ArrowLeft, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import {
  activateCollaboration,
  cancelCollaboration,
  completeCollaboration,
  getCollaboration,
  sendCollaboration,
  updateCollaboration,
} from "@/lib/industry/collaborations";
import { CollaborationForm } from "@/components/industry/collaborations/collaboration-form";
import { CollaborationActions } from "@/components/industry/collaborations/collaboration-actions";
import { CollaborationStatusBadge } from "@/components/industry/collaborations/collaboration-status-badge";
import {
  RECIPIENT_TYPE_LABELS,
  type CollaborationCreate,
  type IndustryCollaboration,
} from "@/types/industry-collaboration";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; collaboration: IndustryCollaboration };

type LifecycleAction = "send" | "activate" | "complete" | "cancel";

const ACTION_COPY: Record<
  LifecycleAction,
  { title: string; description: string; confirm: string; destructive: boolean; done: string }
> = {
  send: {
    title: "Send this proposal?",
    description: "The recipient will be able to see it and respond.",
    confirm: "Send",
    destructive: false,
    done: "Proposal sent.",
  },
  activate: {
    title: "Activate this collaboration?",
    description: "This marks the collaboration as formally underway.",
    confirm: "Activate",
    destructive: false,
    done: "Collaboration activated.",
  },
  complete: {
    title: "Mark this collaboration as completed?",
    description: "This can't be undone.",
    confirm: "Complete",
    destructive: false,
    done: "Collaboration completed.",
  },
  cancel: {
    title: "Cancel this collaboration?",
    description: "This can't be undone.",
    confirm: "Cancel Collaboration",
    destructive: true,
    done: "Collaboration cancelled.",
  },
};

const RUNNERS: Record<LifecycleAction, (id: string) => Promise<IndustryCollaboration>> = {
  send: sendCollaboration,
  activate: activateCollaboration,
  complete: completeCollaboration,
  cancel: cancelCollaboration,
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

export function CollaborationDetailView({
  collaborationId,
  initialEdit = false,
}: {
  collaborationId: string;
  initialEdit?: boolean;
}) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState(initialEdit);

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [pendingAction, setPendingAction] = useState<LifecycleAction | null>(null);
  const [confirming, setConfirming] = useState<LifecycleAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCollaboration(collaborationId)
      .then((collaboration) => {
        if (!cancelled) setState({ status: "ready", collaboration });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this collaboration."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [collaborationId, reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function handleSave(data: CollaborationCreate) {
    setSaving(true);
    setFormError(null);
    try {
      const updated = await updateCollaboration(collaborationId, {
        title: data.title,
        description: data.description,
      });
      setState({ status: "ready", collaboration: updated });
      setEditing(false);
      setActionSuccess("Changes saved.");
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "Could not save your changes. Please try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function runAction(action: LifecycleAction) {
    setConfirming(null);
    setPendingAction(action);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await RUNNERS[action](collaborationId);
      setState({ status: "ready", collaboration: updated });
      setActionSuccess(ACTION_COPY[action].done);
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="space-y-6">
      <Link
        href="/industry/collaborations"
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> All collaborations
      </Link>

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {state.error.status === 404
                  ? "This collaboration doesn't exist or isn't yours."
                  : state.error.status === 401
                    ? "Your session has expired. Please sign in again."
                    : "Could not load this collaboration."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status === 404 ? (
              <Button variant="outline" size="sm" render={<Link href="/industry/collaborations" />}>
                Back to collaborations
              </Button>
            ) : state.error.status !== 401 ? (
              <Button variant="outline" size="sm" onClick={reload}>
                <RefreshCw className="size-3.5" /> Try again
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        <>
          <FormError message={actionError} />
          <FormSuccess message={actionSuccess} />

          {editing ? (
            <>
              <h1 className="text-xl font-semibold">Edit Collaboration</h1>
              <CollaborationForm
                mode="edit"
                initial={state.collaboration}
                submitting={saving}
                error={formError}
                onSubmit={handleSave}
                onCancel={() => {
                  setEditing(false);
                  setFormError(null);
                }}
              />
            </>
          ) : (
            <ReadView
              collaboration={state.collaboration}
              pending={pendingAction !== null}
              canEdit={state.collaboration.status === "DRAFT"}
              onEdit={() => setEditing(true)}
              onSend={() => setConfirming("send")}
              onActivate={() => setConfirming("activate")}
              onComplete={() => setConfirming("complete")}
              onCancel={() => setConfirming("cancel")}
            />
          )}
        </>
      ) : null}

      <ConfirmationDialog
        open={confirming !== null}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={confirming ? ACTION_COPY[confirming].title : ""}
        description={confirming ? ACTION_COPY[confirming].description : undefined}
        confirmLabel={confirming ? ACTION_COPY[confirming].confirm : "Confirm"}
        destructive={confirming ? ACTION_COPY[confirming].destructive : false}
        loading={pendingAction !== null}
        onConfirm={() => confirming && runAction(confirming)}
      />

      {state.status === "ready" && !editing ? (
        <p className="text-right">
          <Button variant="ghost" size="sm" onClick={() => router.push("/industry/collaborations")}>
            Done
          </Button>
        </p>
      ) : null}
    </div>
  );
}

function ReadView({
  collaboration,
  pending,
  canEdit,
  onEdit,
  onSend,
  onActivate,
  onComplete,
  onCancel,
}: {
  collaboration: IndustryCollaboration;
  pending: boolean;
  canEdit: boolean;
  onEdit: () => void;
  onSend: () => void;
  onActivate: () => void;
  onComplete: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold">{collaboration.title}</h1>
            <CollaborationStatusBadge status={collaboration.status} />
          </div>
          <p className="text-xs text-muted-foreground">
            Created {formatDate(collaboration.created_at)} · Updated {formatDate(collaboration.updated_at)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canEdit ? (
            <Button size="sm" variant="outline" onClick={onEdit} disabled={pending}>
              Edit
            </Button>
          ) : null}
          <CollaborationActions
            status={collaboration.status}
            pending={pending}
            onSend={onSend}
            onActivate={onActivate}
            onComplete={onComplete}
            onCancel={onCancel}
          />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recipient</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2">
            {collaboration.recipient_name ? (
              <div className="space-y-0.5">
                <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Name</dt>
                <dd className="text-sm">{collaboration.recipient_name}</dd>
              </div>
            ) : null}
            <div className="space-y-0.5">
              <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Type</dt>
              <dd className="text-sm">{RECIPIENT_TYPE_LABELS[collaboration.recipient_type]}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Description</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm whitespace-pre-line">{collaboration.description}</p>
        </CardContent>
      </Card>
    </div>
  );
}
